docker run \
-it --rm \
--mount type=bind,source=/Users/$USER/projects/github.com/SUSE/soliddriver-checks,target=/root/source_codes \
--mount type=bind,source=/Users/$USER/projects/fujitsu/kmps-15-sp2,target=/root/rpms \
--mount type=bind,source=/Users/$USER/codes/tmp,target=/root/output_dir \
opensuse-leap-soliddriver-checks:latest /bin/bash
