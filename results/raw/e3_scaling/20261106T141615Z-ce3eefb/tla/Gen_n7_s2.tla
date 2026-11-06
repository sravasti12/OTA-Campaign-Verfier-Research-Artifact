---- MODULE Gen_n7_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu02">>, <<"ecu05", "ecu03">>}
====
