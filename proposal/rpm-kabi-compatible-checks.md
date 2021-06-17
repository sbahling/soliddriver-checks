# RPM KABI compatible checks

RPM KABI compatible checks can ensure the KMP RPM can be installed and
running on the targeting OS properly.

## The architect/steps in the application could be

- All the current supported SLES kernel KABI should be stored in 1 or
  separated files. The KABI information can be get via command
  ```zcat /boot/symvers-$(uname -r).gz > ./Module.symvers```
- After user runs rpm checks, the application should load all the
  ```Module.symvers``` files into memory.
- Use ```rpm -q --requires $RPM``` command to get all the KABI name and checksum.
- Compare the KABI name and checksum with all the current supported SLES kernel KABI.
- Put the check result in the RPM check result table (The column name
  could be "KABI compatibility"). The check result is a list of compatible OS.
