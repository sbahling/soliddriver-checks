docker run \
-it --rm \
--mount type=bind,source=/Users/$USER/projects/github.com/SUSE/soliddriver-checks,target=/root/source_codes \
--mount type=bind,source=/Users/$USER/projects/Lenovo/SSDP/01-Apr-2022,target=/root/rpms \
--mount type=bind,source=/Users/$USER/codes/soliddriver-check-output,target=/root/output_dir \
--mount type=bind,source=/Users/$USER/codes/soliddriver-check-runtime/lib/modules,target=/lib/modules \
--mount type=bind,source=/Users/$USER/codes/soliddriver-check-runtime/rpm,target=/var/lib/rpm \
opensuse-leap-soliddriver-checks:latest /bin/bash
