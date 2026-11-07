---- MODULE Gen_n8_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07"}
GenDeps == {<<"ecu06", "ecu01">>, <<"ecu07", "ecu03">>, <<"ecu07", "ecu04">>}
====
