# nl2gcode-cnc-thesis
Natural Language to G-code Translation for CNC grinding using NLU and LLM approaches

This repository contains the dataset, code, and experiments for the Master's thesis:

"First Understand, Then Act: From Natural Language to Instructions to Machines in a Real Industrial Setting"

Author: Sara Samiei  
University of Genoa – MSc Computer Science

## Repository Structure

dataset/
Natural language – G-code dataset (~500 pairs).

rasa/
Implementation of the structured NLU pipeline using Rasa.

notebooks/
Experiments using FLAN-T5, LLaMA-3.1, and LangChain.

thesis/
Final thesis document.

## Goal

Investigate whether natural language operator commands can be translated into safe and executable CNC G-code instructions.
