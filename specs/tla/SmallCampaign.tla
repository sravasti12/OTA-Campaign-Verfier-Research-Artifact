---- MODULE SmallCampaign ----
\* The campaign from examples/parallel_campaign.json: brake v2 requires gateway v2.
EXTENDS OTACampaign

SmallECUs == {"gateway", "brake", "infotainment"}
SmallDeps == {<<"brake", "gateway">>}
====
