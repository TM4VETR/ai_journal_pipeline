# Processing and Linking Vocational Documents

*This repository will be made public.*

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

## Pipeline
The document processing pipeline is located in the *pipeline* subfolder and based on OCR4All. 
You can build and run the Docker containers by:

```
docker compose build
docker compose up -d
```

After the containers are running, open:
* OCR4All UI: http://localhost:8080
* Neo4j Browser: http://localhost:7474 (default credentials: neo4j / secret)

## Evaluation
The evaluation scripts are located in the *evaluation* subfolder.

<ToDo>

## Contact

For questions or collaboration, please contact [Alexander Esser](mailto:alexander.esser@bibb.de). 
