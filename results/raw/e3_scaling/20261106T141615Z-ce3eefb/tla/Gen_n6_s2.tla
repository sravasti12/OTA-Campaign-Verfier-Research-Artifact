---- MODULE Gen_n6_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu03", "ecu01">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu03">>}
====
