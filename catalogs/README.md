# Catalog sources

CDMS entries (https://cdms.astro.uni-koeln.de/classic/entries/), fixed-width
`.cat` files, one folder per species. The viewer reads CSV files produced from
them:

```
linecat convert --catalogs catalogs
```

Generated `CDMS_<species>.csv` files are ignored by git.
