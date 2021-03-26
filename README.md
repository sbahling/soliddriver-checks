# soliddriver-checks

A tool for ```RPM(s)``` and ```installed/running drivers``` checking, with this tool, users can have an overview of their RPM(s) and drivers status:

 - RPM(s): checks ```vendor```, ```signature```, ```distribution``` and ```supported``` flag for drivers.

 - Drivers: checks ```supported``` flag, ```SUSE release```, ```running``` and ```RPM name```.

```vendor```: A RPM should have a vendor name. </br>
```signature```: Confirm the signature is from the vendor above. </br>
```distribution```: </br>
```supported flag```: The values of the flag respensent:
  - yes: This driver is supported by SUSE. But please confirm with SUSE if you're not sure if it's really supported by SUSE or the auther of the driver just put a ```yes``` on it.
  - external: This driver is supported by both vendor and SUSE.
  - Missing or no: The driver is not supported by SUSE, please contact the one who provide it to you for any issues.

# Examples:
 - Check RPMs: </br>
   ```bash
   # generate a html report for your rpm checks.
   python solid_driver_checks.py -d /path/to/your/rpm/directory -o html -of name.html
   ```

 - Check all drivers on the system.
    ```bash
    # generate reports with html, excel, pdf format of your os.
    python solid_driver_checks.py -s -o all -od reports
    ```

 - Check remote drivers.
   1. Put all your server information in a json config file, for example:
   ```json
   {
    "servers": [
      {
        "check": "True",
        "ip": "10.67.17.139",
        "user": "username",
        "password": "password",
        "ssh_port": 22,
        "query": "suse"
      },
      {
		"check": "True",
		"ip": "10.67.18.39",
		"user": "username",
		"password": "password",
		"ssh_port": 22,
		"query": "vendor"
	}
    ]
   }
   ```
   ```query```: respensent the supported flag you can give all, suse, vendor, unknow to it.

   2. Run the command below:
   ```bash
   # generate excel report of your remote servers.
   python solid_driver_checks.py -e config.json
   ```