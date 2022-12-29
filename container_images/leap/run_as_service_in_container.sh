#!/bin/bash
docker run -d  -p 9090:8080 \
--mount type=bind,source=/lib/modules,target=/lib/modules \
--mount type=bind,source=/var/lib/rpm,target=/var/lib/rpm \
leap-sdc /bin/bash
