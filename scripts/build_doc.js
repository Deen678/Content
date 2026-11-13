#!/usr/bin/env node
// Builds the site content Word document: page by page, section by section,
// every text box with its Figma layer, target word count, the new text and its word count.
// Usage: node scripts/build_doc.js sites/<domain>/content.json [out.docx]
const fs = require('fs'), path = require('path');
const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, AlignmentType, HeadingLevel, Footer, PageNumber } = require('docx');

const args = process.argv.slice(2);
const pageArg = args.includes('--page') ? args[args.indexOf('--page') + 1].toLowerCase() : null;
const pos = args.filter((a, i) => !a.startsWith('--') && args[i - 1] !== '--page');
const contentPath = pos[0];
const dir = path.dirname(contentPath);
const content = JSON.parse(fs.readFileSync(contentPath, 'utf8'));
const figma = JSON.parse(fs.readFileSync(path.join(dir, 'figma.json'), 'utf8'));
const out = pos[1] || path.join(dir, `Site-Content-${content.site}-${new Date().toISOString().slice(0, 10)}.docx`);
const text = Object.fromEntries(content.boxes.map(b => [b.id, b.text]));
const kept = new Set(content.boxes.filter(b => b.keep).map(b => b.id));
const shown = new Set(content.boxes.filter(b => b.keep && b.show).map(b => b.id));  // tone-setting lines kept as designed, shown in grey for the overview
// "~~old~~ new" = struck-out words shown with a line through them (the design's edit effect).
const ACCENT = 'C8102E';  // red italic accent words, as in the design
const runsFor = (line, o) => line.split(/(~~[^~]+~~|\*[^*]+\*)/).filter(Boolean).map(seg => seg.startsWith('~~')
  ? new TextRun({ text: seg.slice(2, -2), font: F, size: o.size, strike: true, color: '9CA3AF' })
  : seg.startsWith('*') ? new TextRun({ text: seg.slice(1, -1), font: F, size: o.size, bold: o.bold, italics: true, color: o.color || ACCENT })
  : new TextRun({ text: seg, font: F, size: o.size, bold: o.bold, color: o.color, italics: o.italics }));
const words = t => (String(t || '').match(/[A-Za-z0-9£$€%&@#'’\-]+(?:[.,][0-9]+)?/g) || []).length;
const F = 'Arial', NAVY = '1F3864', MUTED = '6B7280';
const t = (s, o = {}) => new TextRun({ text: s, font: F, size: o.size || 20, bold: o.bold, color: o.color, italics: o.italics });
const border = { style: BorderStyle.SINGLE, size: 4, color: 'D9DEE7' }; const none = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const W = [1500, 6326, 1200]; // 9026
const cell = (runs, w, o = {}) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders: { top: none, left: none, right: none, bottom: border },
  shading: o.fill ? { type: ShadingType.CLEAR, fill: o.fill, color: 'auto' } : undefined, margins: { top: 80, bottom: 80, left: 120, right: 120 },
  children: (Array.isArray(runs[0]) ? runs : [runs]).map(r => new Paragraph({ alignment: o.right ? AlignmentType.RIGHT : AlignmentType.LEFT, keepNext: o.keep, children: r })) });
const ROLE = { heading: 'Heading', paragraph: 'Paragraph', button: 'Button', label: 'Label' };

// Only the boxes whose text is being replaced; anything kept as designed is left out.
const boxes = figma.boxes.filter(b => !b.repeat_of && (!pageArg || b.page.toLowerCase() === pageArg) && (!kept.has(b.id) || shown.has(b.id)));
const children = [
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(`Site content: ${content.site}`)] }),
  new Paragraph({ spacing: { after: 120 }, children: [t(`Written to the Figma design "${figma.figma_file || ''}"  ·  ${new Date().toISOString().slice(0, 10)}`, { color: MUTED })] }),
  ...(shown.size ? [new Paragraph({ spacing: { after: 200 }, children: [t('Black text is new: paste it into the matching Figma box. Grey text is unchanged from the design and is only here so the page reads as a whole.', { color: MUTED, size: 18 })] })] : []),
];
// Plain reading copy: each piece of text on its own line, in page order, ready to copy into Figma.
// Headings and buttons in bold; everything else as normal text. No tables, types or counts.
let lastPage = null, lastSection = null;
for (const b of boxes) {
  if (b.page !== lastPage) { children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: lastPage !== null, children: [new TextRun(b.page.charAt(0).toUpperCase() + b.page.slice(1))] })); lastPage = b.page; lastSection = null; }
  if (b.section !== lastSection) { children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(b.section.charAt(0).toUpperCase() + b.section.slice(1))] })); lastSection = b.section; }
  let txt = text[b.id] || '(not written)';
  if (kept.has(b.id) && !txt.includes('*')) for (const w of (b.accent || [])) txt = txt.replace(w, `*${w}*`);  // kept lines keep the design's italic accent
  const strong = b.role === 'heading' || b.role === 'button';
  const lines = txt.split('\n');
  const grey = shown.has(b.id);
  const o = { size: b.role === 'heading' ? 24 : 21, bold: strong, color: grey ? '9CA3AF' : undefined };
  const runs = []; lines.forEach((line, i) => { if (i) runs.push(new TextRun({ break: 1 })); runs.push(...runsFor(line, o)); });
  children.push(new Paragraph({ spacing: { after: 200 }, keepNext: b.role === 'heading', children: runs }));
}
const doc = new Document({
  styles: { default: { document: { run: { font: F, size: 20 } } }, paragraphStyles: [
    { id: 'Title', name: 'Title', basedOn: 'Normal', run: { font: F, size: 40, bold: true, color: NAVY }, paragraph: { spacing: { before: 0, after: 60 }, keepNext: true } },
    { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 30, bold: true, color: NAVY }, paragraph: { spacing: { before: 200, after: 120 }, keepNext: true, outlineLevel: 0 } },
    { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true, run: { font: F, size: 23, bold: true, color: '2F5496' }, paragraph: { spacing: { before: 200, after: 80 }, keepNext: true, outlineLevel: 1 } }] },
  sections: [{ properties: { page: { margin: { top: 1200, bottom: 1200, left: 1440, right: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: `Site content: ${content.site}  ·  Page `, size: 16, color: '9CA3AF' }), new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '9CA3AF' })] })] }) },
    children }],
});
Packer.toBuffer(doc).then(buf => { fs.writeFileSync(out, buf); console.log('Saved', out); });
