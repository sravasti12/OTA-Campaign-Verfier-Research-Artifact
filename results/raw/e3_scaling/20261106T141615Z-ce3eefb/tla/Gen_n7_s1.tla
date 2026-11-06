---- MODULE Gen_n7_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu03", "ecu02">>, <<"ecu04", "ecu00">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu03">>, <<"ecu06", "ecu04">>}
====
