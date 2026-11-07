---- MODULE Gen_n10_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu00">>, <<"ecu04", "ecu03">>, <<"ecu05", "ecu02">>, <<"ecu05", "ecu03">>, <<"ecu06", "ecu01">>, <<"ecu06", "ecu05">>, <<"ecu08", "ecu05">>, <<"ecu09", "ecu03">>}
====
