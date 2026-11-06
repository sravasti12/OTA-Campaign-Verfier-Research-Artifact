---- MODULE Gen_n10_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu04", "ecu01">>, <<"ecu06", "ecu01">>, <<"ecu06", "ecu02">>, <<"ecu07", "ecu03">>}
====
