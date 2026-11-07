---- MODULE Gen_n6_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu03", "ecu00">>, <<"ecu03", "ecu01">>}
====
