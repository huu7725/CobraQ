const fs = require('fs');
const html = fs.readFileSync('d:/CobraQ/CobraQ_v3.html', 'utf8');
const scripts = html.match(/<script>([\s\S]*?)<\/script>/g) || [];
console.log(`Found ${scripts.length} script blocks`);

scripts.forEach((script, i) => {
    const code = script.replace(/<\/?script>/g, '');
    try {
        new Function(code);
        console.log(`Script block ${i}: OK`);
    } catch(e) {
        console.log(`Script block ${i}: SYNTAX ERROR at char ${e.message.match(/at position (\d+)/)?.[1] || 'unknown'}`);
        console.log(`  ${e.message}`);
        // Find the line
        const pos = parseInt(e.message.match(/at position (\d+)/)?.[1] || 0);
        const before = code.substring(0, pos);
        const line = (before.match(/\n/g) || []).length + 1;
        const lines = code.split('\n');
        console.log(`  Error around line ${line}:`);
        for (let l = Math.max(0, line-2); l < Math.min(lines.length, line+2); l++) {
            console.log(`    ${l+1}: ${lines[l]}`);
        }
    }
});
