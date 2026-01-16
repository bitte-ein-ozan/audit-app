#!/bin/bash
echo "Starting deployment startup script..."

# Attempt to activate environment if it exists
if [ -d "antenv" ]; then
    echo "Activating antenv..."
    source antenv/bin/activate
elif [ -d "/home/site/wwwroot/antenv" ]; then
    echo "Activating /home/site/wwwroot/antenv..."
    source /home/site/wwwroot/antenv/bin/activate
fi

# Ensure requirements are installed
echo "Ensuring requirements are installed..."
python -m pip install -r requirements.txt

echo "Starting Streamlit App..."
python -m streamlit run app.py --server.port 8000 --server.address 0.0.0.0 --server.enableCORS false
