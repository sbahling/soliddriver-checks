# solid-driver-checks

# usage:


Check RPM(s)/driver(s) support status.<br />

optional arguments: <br />
 - -h, --help            show this help message and exit<br />
 - -d DIR, --dir DIR     RPM(s) in this dirctory<br />
 - -r RPM, --rpm RPM     RPM file<br />
 - -s, --system          check drivers running in the system<br />
 - -e REMOTE, --remote config file check remote servers<br />
 - -f FILE, --file FILE  output file name<br />
 - -o {html,excel,terminal,pdf,all}, --output {html,excel,terminal,pdf,all}<br />
                        output to a file<br />
 - -q {suse,vendor,unknow,all}, --query {suse,vendor,unknow,all}<br />
                        only show suse build, vendor build, unknow or all of<br />
                        them<br />

# Examples:

 - Check local RPMs.
 - Check all drivers on the system.
 - Check remote drivers.