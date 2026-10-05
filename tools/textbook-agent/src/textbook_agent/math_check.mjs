import fs from 'node:fs';
import katex from 'katex';
const expressions=JSON.parse(fs.readFileSync(0,'utf8'));
const errors=[];
for (const expr of expressions) {
  try { katex.renderToString(expr,{throwOnError:true,strict:'error',trust:false}); }
  catch (e) { errors.push(String(e.message)); }
}
process.stdout.write(JSON.stringify({errors}));
