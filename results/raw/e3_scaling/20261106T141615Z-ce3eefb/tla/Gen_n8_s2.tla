---- MODULE Gen_n8_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu03", "ecu00">>, <<"ecu06", "ecu04">>, <<"ecu07", "ecu01">>}
====
