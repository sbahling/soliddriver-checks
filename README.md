# soliddriver-checks

A tool for ```KMP(Kernel Module Package)``` and ```installed/running kernel module``` checking, with this tool, users can have an overview of their KMP(s) and kernel modules status:

- KMP (Kernel Module Package)
  - ```Name```: Name of the KMP </br>
  - ```Path```: Path of the KMP’s location </br>
  - ```Vendor```: Who provides this KMP, considered as important issue if there’s no vendor information. </br>
  - ```Signature```: Signature of the KMP, considered as important issue if no signature. </br>
  - ```License```: License followed by the KMP, considered as critical issue if it’s not open sourced license. </br>
  - ```Weak Module Invoked```: The KMP should invoke weak-modules script to determines which modules are KAPI compatible with installed kernels and set up the symlinks. Otherwise it will be considered as critical issue. </br>
- Kernel Module
  - ```Supported Flag```/```Signature```: All the kernel module should have “supported” flag and assigned “external” value to it, otherwise it’s not be supported by SUSE. And all the kernel module should have signature.If the value of “supported” flag is not “external”, or no “supported” flag or no signature, will be considered as critical issue.  </br>
    - The values of the flag respensent:
      - ```yes```: This kernel module is supported by SUSE. But please confirm with SUSE if you're not sure if it's really supported by SUSE or the auther of the kernel module just put a ```yes``` on it.
      - ```external```: This kernel module is supported by both vendor and SUSE.
      - ```Missing or no```: The kernel module is not supported by SUSE, please contact the one who provide it to you for any issues. </br>
  - ```Symbols```: All the symbols in kernel module should be recorded in KMP, otherwise considered as critical issue. </br>

## What you can do with this report generaged by soliddriver-checks?

Regarding the issues listed in the table, please contact your IHV(s) to fix it and follow  [Kernel Module Packages Manual](https://drivers.suse.com/doc/kmpm/) to build SUSE standard KMP.

## Installation

From pypi: ```pip install soliddriver-checks```

From RPM: the rpms can be found on [build.opensuse.org](https://build.opensuse.org/package/show/home:huizhizhao:soliddriver-checks/soliddriver-checks)

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
