---- MODULE Gen_n9_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08"}
GenDeps == {<<"ecu03", "ecu01">>, <<"ecu05", "ecu00">>, <<"ecu05", "ecu04">>, <<"ecu06", "ecu04">>, <<"ecu07", "ecu00">>, <<"ecu07", "ecu03">>, <<"ecu08", "ecu01">>}
====
