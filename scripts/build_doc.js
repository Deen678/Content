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
// "~~old~~ new" = struck-out words shown with a line through them (the design's edit effect).
const runsFor = (line, o) => line.split(/(~~[^~]+~~)/).filter(Boolean).map(seg => seg.startsWith('~~')
  ? new TextRun({ text: seg.slice(2, -2), font: F, size: o.size, strike: true, color: '9CA3AF' })
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

const boxes = figma.boxes.filter(b => !b.repeat_of && (!pageArg || b.page.toLowerCase() === pageArg));
const children = [
  new Paragraph({ heading: HeadingLevel.TITLE, children: [new TextRun(`Site content: ${content.site}`)] }),
  new Paragraph({ spacing: { after: 120 }, children: [t(`Written to the Figma design "${figma.figma_file || ''}"  ·  ${new Date().toISOString().slice(0, 10)}`, { color: MUTED })] }),
  new Paragraph({ spacing: { after: 60 }, children: [t('Business: ', { bold: true, size: 22 }), t(content.business_model || '', { size: 22 })] }),
  new Paragraph({ spacing: { after: 200 }, children: [t('Word counts: headings, buttons and labels match the design exactly; paragraphs are within 10%. Text that repeats across pages (menus, footer, shared buttons) is written once. Grey rows are kept exactly as designed (menu, footer links, form labels, UI hints, service names and prices). Words with a line through them are the struck-out "before" text the design shows.', { color: MUTED, size: 18 })] }),
];
let lastPage = null, rows = [], lastSection = null;
const flush = () => { if (rows.length) { children.push(new Table({ width: { size: 9026, type: WidthType.DXA }, columnWidths: W, rows }), new Paragraph({ spacing: { after: 160 }, children: [] })); rows = []; } };
for (const b of boxes) {
  if (b.page !== lastPage) { flush(); children.push(new Paragraph({ heading: HeadingLevel.HEADING_1, pageBreakBefore: lastPage !== null, children: [new TextRun(b.page)] })); lastPage = b.page; lastSection = null; }
  if (b.section !== lastSection) { flush(); children.push(new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(b.section)] }));
    rows.push(new TableRow({ tableHeader: true, children: [cell([t('Type', { bold: true, color: MUTED, size: 16 })], W[0], { keep: true }), cell([t('Content', { bold: true, color: MUTED, size: 16 })], W[1], { keep: true }), cell([t('Words', { bold: true, color: MUTED, size: 16 })], W[2], { right: true, keep: true })] }));
    lastSection = b.section; }
  const txt = text[b.id] || '(not written)'; const n = words(txt);
  const isHead = b.role === 'heading'; const keep = kept.has(b.id);
  rows.push(new TableRow({ cantSplit: true, children: [
    cell([[t(ROLE[b.role] || b.role, { bold: true, size: 18, color: keep ? '9CA3AF' : undefined })], [t(keep ? 'keep as designed' : (b.layer || ''), { color: MUTED, size: 14, italics: keep })]], W[0], { fill: keep ? 'F7F7F8' : undefined }),
    cell(txt.split('\n').map(line => runsFor(line, keep ? { size: 18, color: '9CA3AF' } : { size: isHead ? 22 : 20, bold: isHead })), W[1], { fill: keep ? 'F7F7F8' : undefined }),
    cell([[t(`${n}`, { bold: true, size: 18, color: keep ? '9CA3AF' : undefined })], [t(`Figma ${b.target_words}`, { color: MUTED, size: 14 })]], W[2], { right: true, fill: keep ? 'F7F7F8' : undefined }),
  ] }));
}
flush();
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
