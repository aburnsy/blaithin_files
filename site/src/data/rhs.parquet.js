// Data loader: streams data/rhs.parquet into the site build.
// Observable Framework runs data loaders with CWD = site/, so ../data/ resolves
// to the repo's data/ directory.
import {createReadStream} from "node:fs";
import {pipeline} from "node:stream/promises";

await pipeline(
  createReadStream("../data/rhs.parquet"),
  process.stdout,
);
