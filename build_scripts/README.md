
# MKDD Extender - Build Scripts

## Linux

```shell
cd /path/to/mkdd-extender/build_scripts

# Clear previous images and cache.
docker system prune -a

# Create the image.
docker build -t mkddextender -f Dockerfile.ubuntu22.04 .

# Spawn the container and run the build script.
docker run -ti -v $PWD:/build_scripts -v ~/Downloads:/output mkddextender /bin/bash /build_scripts/build.sh
```

## Windows

```bat
cd C:\path\to\mkdd-extender\build_scripts

@REM Run the build script.
build.bat
```
