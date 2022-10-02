# Measuring filesystem Operations on AWS EC2 Instances

The repository contains a project, which aims to measure filesystem operations performed on dynamically initialized AWS EC2 instances. The project 
only works with free-tier AMIs. The project works with a fixed number of files - 1000, and a fixed size of each file - 1MB.

## Usage

**tldr & ootb:**

```
$ git clone git@github.com:nbaldzhiev/aws-filesystem-operations-measurement.git && cd aws-filesystem-operations-measurement
$ python3.8 -m venv venv && source venv/bin/activate && pip install -r requirements.txt
$ export AWS_ACCESS_KEY_ID=access-key-id && export AWS_SECRET_ACCESS_KEY=secret-access-key && export AWS_REGION=region
$ python run_orchestrator.py
OR
$ python run_orchestrator.py --human-readable
```

### In more detail

1. A Click-decorated function (command) gets called, which creates an `Orchestrator` (a context-manager class) object.
  * This Click command can receive one optional flag option - `--human-readable`, which causes the results to be parsed into a human readable format. Otherwise, JSON is used.
2. A configurable list of EC2 instances is fed to an Orchestrator class, which creates these instances.
  * A unique key pair and security group is created alongside each instance.
3. Each instance is rebooted, which triggers the operations copy, move and delete to execute on each instance, using a set of dynamically created 1000 files, 
each 1MB in size (not configurable).
  * The operations are performed through a bash script, which is first transferred to the corresponding instance.
  * The reboot is achieved by configuring the crontab of each instance to run the aforementioned bash script upon start-up, achieved through another bash script.
4. The Orchestrator class waits for each instance to finish with the operations.
5. The results of each instance are transferred from each EC2 instance to the `Orchestrator` host.
6. The results of each instance get parsed and printed to the standart output.
7. Each EC2 instance, together with its key pair and security group, are deleted upon exiting the `Orchestrator` context-manager.

## Requirements

* Python 3.8;
* Valid EMI user - this is especially important as an access key ID and a secret access key are required in order to successfully authorize with AWS.

## Notable external packages used

* [boto3](https://github.com/boto/boto3) - providing an AWS SDK for Python.
* [paramiko](https://www.paramiko.org/) - providing SSH client implementation in Python;
* [click](https://github.com/pallets/click) - providing Python CLI toolkit;
* [scp](https://github.com/jbardin/scp.py) - providing SCP client implementation in Python.
