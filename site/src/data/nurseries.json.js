// Data loader: converts config/nurseries.yaml → JSON for use in the site build.
// Observable Framework runs data loaders with CWD = site/, so ../config/ resolves
// to the repo's config/ directory.
import {readFile} from "node:fs/promises";
import {parse} from "yaml";

const yaml = await readFile("../config/nurseries.yaml", "utf8");
const data = parse(yaml);
process.stdout.write(JSON.stringify(data, null, 2));
