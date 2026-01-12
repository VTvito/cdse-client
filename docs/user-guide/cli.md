# CLI

The `cdse` command is installed with the package:

```bash
pip install cdse-client
cdse --help
```

## Search

```bash
cdse search --bbox 9.0,45.0,9.5,45.5 -s 2025-06-01 -e 2025-06-30 -c 20 -l 5
```

## Download

```bash
cdse download --name S2A_MSIL2A_20240115T102351...
cdse download --uuid a1b2c3d4-e5f6-... --checksum
cdse download --uuid a1b2c3d4-e5f6-... --quicklook
```

## Collections

```bash
cdse collections
```
