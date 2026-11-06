---- MODULE Gen_n9_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu03", "ecu01">>, <<"ecu05", "ecu01">>, <<"ecu07", "ecu04">>, <<"ecu07", "ecu06">>}
====
