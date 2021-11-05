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

## Installation

From pypi: ```pip install soliddriver-checks```

From RPM: the rpms can be found on [build.opensuse.org](https://build.opensuse.org/package/show/home:huizhizhao/soliddriver-checks)

## Usage

```
Usage: soliddriver-checks [OPTIONS] [CHECK_TARGET]

  Run checks against CHECK_TARGET.

  CHECK_TARGET can be:
    rpm file
    directory containing rpm files
    "system" to check locally installed kernel modules
    a config file listing remote systems to check (Please
    ensure your remote systems are scp command accessable)

    default is local system

Options:
  -f, --format [json|html|excel|pdf|all]
  				  Specify output format, default is html,all
				  data can be saved in json format, html|excel|
				  pdf are optimized for better view. The
                                  default output is $(pwd)/check_result.json
  -q, --query [suse|other|unknown|all]
                                  Filter results based on vendor tag from rpm
                                  package providing module. "suse" = SUSE,
                                  "other" = other vendors, "unknown" = vendor
                                  is unknown, "all" = show all (default)

  -o, --output TEXT               Output destination. Target can be filename
                                  or point existing directory If directory,
                                  files will be placed in the directory using
                                  a autmatically generated filename. If target
                                  is not an existing directory, file name is
                                  assumed and output files will use the path
                                  and file name specified. In either case, the
                                  file extension will be automatically
                                  appended matching on the output format
```

## Examples:
 - Check RPMs: </br>
   ```bash
   # generate a html report for your rpm checks as default output.
   soliddriver-checks /path/to/your/rpm/directory
   ```

 - Check all drivers on the system.
    ```bash
    # generate reports with html, excel, pdf format of your os.
    soliddriver-checks
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
        "query": "all"
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
   soliddriver-checks ./config.json
   ```
