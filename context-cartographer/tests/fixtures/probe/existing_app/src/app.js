const catalogue = require("./catalogue");

function main(argv) {
  const date = argv[2] || new Date().toISOString().slice(0, 10);
  const readings = catalogue.forDate(date);
  for (const reading of readings) {
    console.log(`${reading.reference}  ${reading.title}`);
  }
}

main(process.argv);
