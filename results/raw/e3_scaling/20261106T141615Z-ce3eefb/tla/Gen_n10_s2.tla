---- MODULE Gen_n10_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu00">>, <<"ecu09", "ecu04">>, <<"ecu09", "ecu08">>}
====
