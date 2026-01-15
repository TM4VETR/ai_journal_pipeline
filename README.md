# Processing and Linking Vocational Documents

This repository contains the code (for both the document processing pipeline and evaluation) for our article "Processing and Linking Vocational Documents" in the AI special issue *Integrating Data Sources for Smarter Interdisciplinary AI Solutions: Challenges and Opportunities*, MDPI, 2026.

## Overview
Our article describes the construction of a complete document processing pipeline for German Vocational Education and Training (VET) documents, beginning with document preprocessing, via information extraction, to linking the document to an ontology in form of a knowledge graph.  

Technologies used include OCR4All (Docker setup), Python-based extraction modules, and Neo4j for knowledge graph storage and querying.

## Citation
If you use this code, please cite:

```bibtex
@article{Esser2026Processing,
  title        = {Processing and Linking Vocational Documents},
  author       = {Esser, Alexander M. and Reiser, Thomas},
  journal      = {AI},
  note         = {Special Issue: Integrating Data Sources for Smarter Interdisciplinary AI Solutions: Challenges and Opportunities},
  year         = {2026},
  publisher    = {MDPI},
  volume       = {<volume>},
  number       = {<issue>},
  pages        = {<pages>},
  doi          = {<DOI>},
}
```

## Getting started

### Environment variables
You can set environment variables in a `.env` file in the root directory. These will be loaded using *dotenv*.  
To get started, you can simply copy the provided *template.env* file to *.env* and modify the variables as needed.


### Required data
The occupation coding module requires the list of occupations provided by the Federal Employment Agency of Germany (Bundesagentur für Arbeit): [Gesamtberufsliste_der_BA.xlsx](https://rest.arbeitsagentur.de/infosysbub/download-portal-rest/ct/dkz-downloads/Gesamtberufsliste_der_BA.xlsx)

You can download it by running
```bash
cd custom/oc
python -m utils.data_util
```

### NER model
The model for Named Entity Recognition (NER) needs to be copied into the `custom/models` folder manually.


### Folder structure

OCR4All expects a specific folder structure for project. You can create the necessary folders by once executing:

```
create_folder_structure.cmd
```


## Pipeline
You can build and run the Docker containers by:

```
docker compose build
docker compose up -d
```

When the containers are running, you can open:
* Web interface: http://localhost:5000/upload
* OCR4All: http://localhost:8080
* Neo4j: http://localhost:7474


## Evaluation
The evaluation scripts are located in the *evaluation* subfolder.


## Contact
For questions or collaboration, please contact [Alexander Esser](mailto:alexander.esser@bibb.de). 
