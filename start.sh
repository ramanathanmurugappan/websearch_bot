#!/bin/bash
rm -f /tmp/.X99-lock
Xvfb :99 -screen 0 1024x768x16 &
sleep 1
streamlit run app.py
