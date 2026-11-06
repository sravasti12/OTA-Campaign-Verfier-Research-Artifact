---- MODULE Gen_n8_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07"}
GenDeps == {<<"ecu02", "ecu00">>, <<"ecu04", "ecu00">>, <<"ecu04", "ecu02">>}
====
