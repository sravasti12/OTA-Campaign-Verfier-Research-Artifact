---- MODULE Gen_n20_s1 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09", "ecu10", "ecu11", "ecu12", "ecu13", "ecu14", "ecu15", "ecu16", "ecu17", "ecu18", "ecu19"}
GenDeps == {<<"ecu01", "ecu00">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu02">>, <<"ecu06", "ecu04">>, <<"ecu08", "ecu06">>, <<"ecu09", "ecu03">>, <<"ecu13", "ecu02">>, <<"ecu14", "ecu06">>, <<"ecu16", "ecu07">>, <<"ecu16", "ecu09">>, <<"ecu17", "ecu04">>, <<"ecu18", "ecu13">>, <<"ecu19", "ecu10">>, <<"ecu19", "ecu16">>}
====
