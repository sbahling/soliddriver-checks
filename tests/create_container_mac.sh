docker run \
-it \
--mount type=bind,source=/Users/$USER/projects/github.com/SUSE/soliddriver-checks,target=/root/source_codes \
--mount type=bind,source=/Users/$USER/projects/Lenovo/SSDP/01-Apr-2022,target=/root/rpms \
--mount type=bind,source=/Users/$USER/codes/tmp,target=/root/output_dir \
opensuse-leap-soliddriver-checks:latest /bin/bash
