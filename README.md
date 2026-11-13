# Site Content

Writes website content to fit a Figma design: unique to each site, matched
to the business model, and matched to the design's word counts.

## Use
Open this repo in Claude Code and ask:

> Use the content-writer agent to write the content for example.com from this Figma file: <link>. The business sells …

You get a Word document, page by page and section by section, with every text
box's new content and its word count next to the Figma count.

## Rules
- **Word counts:** headings, buttons and labels (and any box of 8 words or
  fewer) match the Figma placeholder **exactly**. Paragraphs are within **±10%**.
- **Unique:** never copies the Figma placeholder, and never shares a 6-word
  phrase with another site's content in this repo.
- **Fits the business model:** real services, pricing and delivery, with no
  invented prices, reviews or statistics.
- No lorem ipsum, [brackets] or TBC.

## Pieces
- `.claude/agents/content-writer.md`: the agent's instructions
- `scripts/figma_extract.py`: reads the Figma file and lists every text box (page, section, type, word count). Uses the Figma token saved in the environment's settings.
- `scripts/check_content.py`: checks the written content against the word counts and rules
- `scripts/build_doc.js`: builds the Word document
- `sites/<domain>/`: each site's `figma.json`, `content.json` and Word document

Requires Python 3 with `requests`, and Node.js with `docx`.
