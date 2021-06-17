SUSE SolidDriver Checks
=======================

The purpose of the SUSE SolidDriver Checks is to ensure best end user
experience by verifying that third party delivered drivers are built and
deployed in a SUSE SolidDriver compliant] manner.

General Features
----------------
*NOTE: Not all features are implemented at this time*

* This tool shall be usable by SUSE, SUSE Partners, and SUSE customers.
* The tool shall be able check running and installed modules on local or
  remote systems
* The tool shall be able check kernel module packages (KMPs) that have not
  been installed
* The tool shall create reports in the following formats:
    - HTML
    - Excel spreadsheet
    - PDF
    - JSON
    - Terminal
* Remote checks executed via ssh preferably using ssh keys for
  authentication


Checks
------
*NOTE: Not all checks are implemented at this time*

* Critical checks failures shall give a high level warning (RED)
* Important checks failures shall give a low level warning (AMBER)


### Kernel Modules

Critical checks

* Kernel modules have `supported` flag properly set
    - `supported` flag appears only once
    - `supported` flag value exactly matches the string `external`
* Kernel modules are installed in the proper location on the system
    - Valid locations:
        - `/lib/modules/$KERNEL-FLAVOR-VERSION/updates`
        - `/lib/modules/$KERNEL-FLAVOR-VERSION/extra`
* Installed module can be traced back to RPM package that installed it.
* Module only exists once under /updates or /extra paths

Important checks

* Kernel modules are digitally signed
* License GPL v2 compatible


### Kernel Module Packages

Critical checks

* RPM contains all the used symbols of all contained modules as
  package `Requires`
* RPM post install script calls the weak-modules2 script
* RPM license matches kernel module license
 
Important checks

* RPM has vendor tag set
* RPM is properly signed
* RPM follows KMP naming convention
* RPM license is GPL v2 compatible

System commands used
--------------------

#### rpm

* Find package that provides a kernel module
* Retrieve package vendor and signature information
* List package requirements (for kernel symbol usage)
* List package scripts (check that weak-modules2 is called)


#### lsmod

* list modules currently running on system

#### modinfo

* Find location of module file when querying running module
* List module signature information
* List supported flag

#### modprobe

* retrieve module symbol information `--dump-modversions`
