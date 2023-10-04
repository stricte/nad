#!/bin/bash

# Ensure that the script is run as root or with sudo privileges if necessary
# Uncomment the following lines if needed
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root or with sudo."
    exit 1
fi

# Define the name of the virtual environment
VENV_NAME="nad"

# Install Python 3 and create a virtual environment
echo "Installing Python 3 and creating a virtual environment..."
apt-get update
apt-get install -y python3 python3-pip virtualenv mosquitto

# Create and activate the virtual environment
echo "Creating and activating virtual environment: $VENV_NAME"
virtualenv -p python3 $VENV_NAME
source $VENV_NAME/bin/activate

# Install necessary Python packages inline
echo "Installing Python packages..."
pip install paho-mqtt daemonize pyserial

# Deactivate the virtual environment
deactivate

echo "Bootstrap completed. To activate the virtual environment, run:"
echo "source $VENV_NAME/bin/activate"
