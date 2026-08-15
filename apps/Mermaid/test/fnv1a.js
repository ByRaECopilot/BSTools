'use strict';
// FNV-1a de 32 bits, offset basis y primo estandar. Referencia independiente
// para verificar el sufijo "_x<hash8>" de classNameFor (ADR-0004 S2bis).
function fnv1a32Hex(str) {
  let h = 0x811c9dc5;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}
module.exports = { fnv1a32Hex };
