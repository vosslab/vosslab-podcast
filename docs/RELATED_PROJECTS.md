# Related projects

## Possible related projects

### github-activity

- Relationship: Same-workflow project or independent implementation.
- Link: https://github-activity.readthedocs.io/en/latest/
- Why visitors may care: Collects dated GitHub pull-request and issue activity as Markdown, which
  can supply a concise project-update input before this repository produces longer content.
- Evidence: Its official documentation describes a GitHub GraphQL library and CLI that render
  activity as Markdown changelogs or community updates.
- Confidence: likely

### GitHub Changelog Generator

- Relationship: Same-workflow project or independent implementation.
- Link: https://github.com/github-changelog-generator/github-changelog-generator
- Why visitors may care: Generates a Markdown changelog from GitHub tags, issues, labels, and
  merged pull requests when a structured release summary is the desired input or final output.
- Evidence: Its project documentation describes a CLI and container workflow that produces a
  `CHANGELOG.md` from GitHub release activity, labels, issues, and pull requests.
- Confidence: possible

### GitHub automatically generated release notes

- Relationship: Companion project, extension, or interoperability tool.
- Link: https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes
- Why visitors may care: Provides a lightweight GitHub-native option when a release-focused update
  is sufficient instead of a daily, evidence-traced narrative.
- Evidence: GitHub's official documentation says it generates release overviews from merged pull
  requests and contributors, with a full-changelog link and configurable categories.
- Confidence: possible

### MkDocs

- Relationship: Companion project, extension, or interoperability tool.
- Link: https://www.mkdocs.org/
- Why visitors may care: Builds the Markdown source that receives the daily publication bundle, so
  visitors can adapt the publisher boundary to a static documentation site.
- Evidence: MkDocs documents its Markdown-and-YAML static-site workflow and static HTML output;
  this repository's daily publisher imports approved posts into a local MkDocs site.
- Confidence: likely

### Keep a Changelog

- Relationship: Domain standard, guide, dataset, or other visitor resource.
- Link: https://keepachangelog.com/en/2.0.0/
- Why visitors may care: Gives makers a human-oriented way to curate notable Git changes before
  turning that work into a broader update for readers.
- Evidence: The guide defines a changelog as a curated, chronological list of notable changes and
  explains that changelogs serve people rather than machine records.
- Confidence: possible

## Evidence notes

These entries come from official project documentation, GitHub documentation, and the Keep a
Changelog guide. They cover adjacent workflow steps: collecting activity, curating a human-readable
change summary, preparing release notes, and publishing Markdown as a static site. No direct
alternative covering the complete GitHub-activity-to-evidence-traced-daily-blog workflow was
confirmed in the two discovery rounds.
