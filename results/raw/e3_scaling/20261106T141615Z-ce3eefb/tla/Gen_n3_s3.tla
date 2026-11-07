---- MODULE Gen_n3_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu00">>}
====
