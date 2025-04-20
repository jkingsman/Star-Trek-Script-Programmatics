# Star-Trek-Script-Programmatics -- Machine Readable Star Trek Scripts!

A collection of Star Trek scripts dumped to JSON. A bit of a messy repo from my work but better the data be out there than not.

`processed` contains TNG and VOY scripts in cleaned JSON mode, grouped per episode. **This is likely what you want if you're doing any kind off automated work.**

`dumps` are the raw complete transcripts of an entire show concatenated together, with limited speaker and location identification.

`csv_dumps` contains a CSV for each show, one row per dialog line, each row containing limited episode and speaker identifiers.

`script converters` contains some of the raw scraping and enrichment logic used to create the script dumps, and is likely of little benefit to anyone that's not me regenerating these from scratch.

Fair warning, these scripts have typos due to human/manual ingestion and conversion problems, and the code to generate and wrangle them is poorly written and hastily slapped together -- please temper expectations.

Special thanks to http://www.chakoteya.net/; their dumps were the source for all this.
