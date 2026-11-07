---- MODULE Gen_n5_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04"}
GenDeps == {<<"ecu04", "ecu00">>, <<"ecu04", "ecu01">>}
====
