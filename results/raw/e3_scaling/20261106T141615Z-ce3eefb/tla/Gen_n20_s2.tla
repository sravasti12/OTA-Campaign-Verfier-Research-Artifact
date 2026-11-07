---- MODULE Gen_n20_s2 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09", "ecu10", "ecu11", "ecu12", "ecu13", "ecu14", "ecu15", "ecu16", "ecu17", "ecu18", "ecu19"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu03", "ecu00">>, <<"ecu07", "ecu00">>, <<"ecu08", "ecu03">>, <<"ecu08", "ecu04">>, <<"ecu09", "ecu04">>, <<"ecu12", "ecu07">>, <<"ecu14", "ecu03">>, <<"ecu14", "ecu08">>, <<"ecu18", "ecu11">>, <<"ecu19", "ecu14">>}
====
