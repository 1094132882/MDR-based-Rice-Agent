# Database availability

The runtime expects Neo4j 5.24.x containing the rice graph plus RGI/MDR registry. Graph schema snapshots are in `methods/s_cot_raps/mdr_schema.json`; KGQA query implementations are in `experiment/tools/`; metadata models are in `rice_Python/App/mdr/` and `rice_Python/App/graph/`. Registration spreadsheets/CSV and update scripts are in `update_graph/`.

The release does not bundle a database dump, biological source corpus, credentials, or a complete biological database construction pipeline. Metadata updates enrich an existing database; they do not create the full rice knowledge graph. An empty Neo4j installation is insufficient. The authors must separately decide how to distribute or describe the actual graph, its source versions, build steps, and redistribution rights if full system reproduction is promised.

Run update scripts only on an intended development copy after inspecting their MATCH/SET statements. Set `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD` in the shell, or export the private `.env` before invoking them. They are never part of normal service startup. Localized registry translation migration scripts and audit outputs are omitted from this runtime release; current backend localization maps and the updated registration tables are included.
