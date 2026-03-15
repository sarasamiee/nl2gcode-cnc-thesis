import re
import json
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

FEED_RATE_RANGES = {
    "F_precise": (5, 6),
    "F_slow": (8, 12),
    "F_medium": (15, 20),
    "F_fast": (25, 30),
}

def detect_f_label(text: str):
    s = text.lower()
    if any(w in s for w in ["spark-out", "spark out", "finishing", "precision", "final pass"]):
        return "F_precise"
    if any(w in s for w in ["fine cut", "fine", "slowly", "slow", "carefully", "careful"]):
        return "F_slow"
    if any(w in s for w in ["light cut", "light", "superficial"]):
        return "F_medium"
    if any(w in s for w in ["rough cut", "rough", "deep", "heavy"]):
        return "F_fast"
    return None

def extract_x(text: str):
    m = re.search(r"\bX(-?\d+)\b", text, flags=re.IGNORECASE)
    return float(m.group(1)) if m else None

def extract_z(text: str):
    m = re.search(r"\bZ(-?\d+)\b", text, flags=re.IGNORECASE)
    return float(m.group(1)) if m else None

def extract_f_explicit(text: str):
    m = re.search(r"\bF\s*(-?\d+)\b", text, flags=re.IGNORECASE)
    return float(m.group(1)) if m else None

def extract_number_only(text: str):
    m = re.fullmatch(r"\s*(-?\d+(\.\d+)?)\s*", text)
    return float(m.group(1)) if m else None

def in_range(f_value: float, f_label: str):
    lo, hi = FEED_RATE_RANGES[f_label]
    return lo <= f_value <= hi

def fmt_num(v: float):
    return int(v) if float(v).is_integer() else v

def build_json(intent: str, x, z, f_value, f_label, gcode):
    entities = {}
    if x is not None:
        entities["x_value"] = fmt_num(x)
    if z is not None:
        entities["z_value"] = fmt_num(z)
    if f_label is not None:
        entities["F_label"] = f_label
    if f_value is not None:
        entities["f_value"] = fmt_num(f_value)

    payload = {"intent": intent, "entities": entities}
    if gcode is not None:
        payload["gcode"] = gcode
    return json.dumps(payload, ensure_ascii=False)

class ActionHandleCommand(Action):
    def name(self):
        return "action_handle_command"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain):
        text = tracker.latest_message.get("text", "")
        intent = tracker.latest_message.get("intent", {}).get("name", "")

        # slots
        x_slot = tracker.get_slot("x_value")
        z_slot = tracker.get_slot("z_value")
        f_slot = tracker.get_slot("f_value")
        label_slot = tracker.get_slot("F_label")
        awaiting_f = tracker.get_slot("awaiting_f") or False

        # parse current message
        x_new = extract_x(text)
        z_new = extract_z(text)
        f_explicit = extract_f_explicit(text)
        f_number_only = extract_number_only(text)

        events = []
        if x_new is not None:
            x_slot = x_new
            events.append(SlotSet("x_value", x_slot))
        if z_new is not None:
            z_slot = z_new
            events.append(SlotSet("z_value", z_slot))

        # -------------------------
        # User replies with number (second turn)
        # -------------------------
        if intent == "inform_f_value" and f_number_only is not None:
            if not awaiting_f or label_slot is None:
                out = build_json("inform_f_value", x_slot, z_slot, f_number_only, label_slot, None)
                dispatcher.utter_message(text=out)
                return events

            lo, hi = FEED_RATE_RANGES[label_slot]
            if not in_range(f_number_only, label_slot):
                dispatcher.utter_message(
                    text=f"{fmt_num(f_number_only)} is not valid for {label_slot}. Choose a value between {lo} and {hi}."
                )
                return events

            f_slot = f_number_only
            events += [SlotSet("f_value", f_slot), SlotSet("awaiting_f", False)]

            gcode = "G01"
            if x_slot is not None:
                gcode += f" X{fmt_num(x_slot)}"
            if z_slot is not None:
                gcode += f" Z{fmt_num(z_slot)}"
            gcode += f" F{fmt_num(f_slot)}"

            out = build_json("grind_linear", x_slot, z_slot, f_slot, label_slot, gcode)
            dispatcher.utter_message(text=out)
            return events

        # -------------------------
        # HOMING (G28)
        # -------------------------
        if intent == "homing":
            out = build_json("homing", None, None, None, None, "G28")
            dispatcher.utter_message(text=out)
            return events

        # -------------------------
        # PURE POSITIONING (G00) ignore feed
        # -------------------------
        if intent == "pure_positioning":
            gcode = "G00"
            if x_slot is not None:
                gcode += f" X{fmt_num(x_slot)}"
            if z_slot is not None:
                gcode += f" Z{fmt_num(z_slot)}"
            out = build_json("pure_positioning", x_slot, z_slot, None, None, gcode)
            dispatcher.utter_message(text=out)
            return events

        # -------------------------
        # GRIND LINEAR (G01)
        # -------------------------
        if intent == "grind_linear":
            if f_explicit is not None:
                f_slot = f_explicit
                events += [SlotSet("f_value", f_slot), SlotSet("awaiting_f", False)]

                gcode = "G01"
                if x_slot is not None:
                    gcode += f" X{fmt_num(x_slot)}"
                if z_slot is not None:
                    gcode += f" Z{fmt_num(z_slot)}"
                gcode += f" F{fmt_num(f_slot)}"

                out = build_json("grind_linear", x_slot, z_slot, f_slot, None, gcode)
                dispatcher.utter_message(text=out)
                return events

            label = detect_f_label(text)
            if label is not None:
                label_slot = label
                events += [SlotSet("F_label", label_slot), SlotSet("awaiting_f", True), SlotSet("f_value", None)]

                out = build_json("grind_linear", x_slot, z_slot, None, label_slot, None)
                dispatcher.utter_message(text=out)

                lo, hi = FEED_RATE_RANGES[label_slot]
                dispatcher.utter_message(
                    text=f"I detected {label_slot}. Which exact F value do you want between {lo} and {hi}?"
                )
                return events

            dispatcher.utter_message(text="Please specify the feed rate for grinding.")
            return events

        dispatcher.utter_message(response="utter_default")
        return events

