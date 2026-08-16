# Provider service icons

Official artwork, used at published colours and never recoloured.

| Source | Licence | Location |
|---|---|---|
| Microsoft Azure Architecture Icons | MIT | `azure/` |
| Google Cloud Icons | Apache 2.0 | `gcp/` |
| AWS — Iconify `logos` set | CC0 / permissive | rendered inline, not stored here |

Only the services WhichCloud actually prices or diagrams are copied in —
seven per provider, ~48 KB total, rather than the 883 icons the two packs
ship.

**AWS is deliberately not in this folder.** Amazon publishes its Architecture
Icons under CC-BY-ND, which forbids derivative works, and resizing or
restyling an icon inside a component is one. The Iconify `logos` equivalents
are used instead.

Sources:
- https://learn.microsoft.com/azure/architecture/icons/
- https://cloud.google.com/icons

## aws/

AWS's official architecture icons, 85 of the 868 they publish, vendored by
`backend/scripts/fetch_aws_icons.py` from awslabs/aws-icons-for-plantuml --
AWS's own repository. Re-run that script to add more; the `WANTED` set at the
top is the list.

These are the marks AWS's published reference architectures are drawn with. A
diagram built from approximations of them reads as an imitation of one, which
is why Iconify's 62-icon `logos` set was replaced: it also left four services
in a real description with no icon at all.

Vendored rather than hotlinked. A diagram has to render with no network, and a
raw.githubusercontent URL is a dependency on someone else's uptime for artwork
that changes about twice a year.
