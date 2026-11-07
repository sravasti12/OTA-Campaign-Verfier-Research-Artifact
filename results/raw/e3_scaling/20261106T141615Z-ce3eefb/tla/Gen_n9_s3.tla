---- MODULE Gen_n9_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08"}
GenDeps == {<<"ecu03", "ecu01">>, <<"ecu07", "ecu04">>, <<"ecu08", "ecu01">>, <<"ecu08", "ecu07">>}
====
