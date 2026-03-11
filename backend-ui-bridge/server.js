'use strict';
const http = require('http');
const port = process.env.PORT || 3001;
const server = http.createServer((_req, res) => {
  res.writeHead(200, {'Content-Type': 'application/json'});
  res.end(JSON.stringify({status:'ok'}));
});
if (require.main === module) {
  server.listen(port, () => console.log(`backend-ui-bridge listening on ${port}`));
}
module.exports = server;
