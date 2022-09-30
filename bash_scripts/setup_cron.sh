#!/bin/bash

# Add new cron job for running the script at startup. We don't care for existing cron jobs so we don't append, but
# create a new crontab instead
echo "@reboot $(pwd)/perform_measurements.sh" > newcron

# Deploy the new crontab
crontab newcron

# Remove the temporary crontab file
rm newcron
