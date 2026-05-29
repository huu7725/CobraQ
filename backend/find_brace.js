const fs = require('fs');
const html = fs.readFileSync('d:/CobraQ/CobraQ_v3.html', 'utf8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
const code = scriptMatch[1];
const lines = code.split('\n');

let braceCount = 0, minBrace = 0;
for (let li = 0; li < lines.length; li++) {
    const line = lines[li];
    for (const ch of line) {
        if (ch === '{') braceCount++;
        if (ch === '}') braceCount--;
    }
    if (braceCount < minBrace) {
        minBrace = braceCount;
        console.log(`Line ${li+1}: Brace depth = ${braceCount} (went negative!)`);
        console.log(`  ${lines[li]}`);
    }
}
console.log(`\nFinal: ${braceCount}, Min: ${minBrace}`);
