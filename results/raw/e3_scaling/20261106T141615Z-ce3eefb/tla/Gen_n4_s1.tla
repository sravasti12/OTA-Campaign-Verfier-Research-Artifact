---- MODULE Gen_n4_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03"}
GenDeps == {<<"ecu02", "ecu00">>, <<"ecu03", "ecu00">>}
====
