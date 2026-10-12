// Receives {expressions:[latex...]} on stdin and emits an array of offline SVG HTML strings.
// Requires node with mathjax-full (already available on many AI authoring runtimes).
const chunks=[];process.stdin.on('data',d=>chunks.push(d));
process.stdin.on('end',()=>{
  const {mathjax}=require('mathjax-full/js/mathjax.js');
  const {TeX}=require('mathjax-full/js/input/tex.js');
  const {SVG}=require('mathjax-full/js/output/svg.js');
  const {liteAdaptor}=require('mathjax-full/js/adaptors/liteAdaptor.js');
  const {RegisterHTMLHandler}=require('mathjax-full/js/handlers/html.js');
  const {AllPackages}=require('mathjax-full/js/input/tex/AllPackages.js');
  const adaptor=liteAdaptor(); RegisterHTMLHandler(adaptor);
  const html=mathjax.document('',{InputJax:new TeX({packages:AllPackages}),OutputJax:new SVG({fontCache:'none'})});
  const expr=JSON.parse(Buffer.concat(chunks).toString('utf8')).expressions;
  const result=expr.map(s=>{
    try {return adaptor.outerHTML(html.convert(s,{display:true}));}
    catch(e){return null;}
  });
  process.stdout.write(JSON.stringify(result));
});
