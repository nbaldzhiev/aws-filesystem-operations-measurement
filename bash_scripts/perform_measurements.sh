#!/bin/bash

N_FILES_TO_CREATE=1000
FILES_SIZE_MB=1

# Create the directories
mkdir source destination

# Files creation operation
start_time=`date +%s%3N`
for i in $(seq $N_FILES_TO_CREATE); do
  dd if=/dev/urandom of=source/output-$i.dat  bs=1M  count=$FILES_SIZE_MB
done
end_time=`date +%s%3N`
elapsed_time=$((end_time-start_time))
echo "CREATE: ${elapsed_time}ms" > results.txt

# Files copy operation
start_time=`date +%s%3N`
cp -a source/. destination/
end_time=`date +%s%3N`
elapsed_time=$((end_time-start_time))
echo "COPY: ${elapsed_time}ms" >> results.txt

# Files deletion operation
start_time=`date +%s%3N`
rm destination/*
end_time=`date +%s%3N`
elapsed_time=$((end_time-start_time))
echo "DELETE: ${elapsed_time}ms" >> results.txt

# Cleanup
rm -rf source/ destination/

echo "DONE" >> results.txt
