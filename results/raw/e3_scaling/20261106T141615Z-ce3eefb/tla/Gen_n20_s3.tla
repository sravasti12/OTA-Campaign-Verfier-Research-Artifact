---- MODULE Gen_n20_s3 ----
EXTENDS OTACampaign
GenECUs == {"ecu00", "ecu01", "ecu02", "ecu03", "ecu04", "ecu05", "ecu06", "ecu07", "ecu08", "ecu09", "ecu10", "ecu11", "ecu12", "ecu13", "ecu14", "ecu15", "ecu16", "ecu17", "ecu18", "ecu19"}
GenDeps == {<<"ecu02", "ecu00">>, <<"ecu02", "ecu01">>, <<"ecu04", "ecu00">>, <<"ecu04", "ecu01">>, <<"ecu05", "ecu00">>, <<"ecu08", "ecu07">>, <<"ecu09", "ecu01">>, <<"ecu09", "ecu07">>, <<"ecu10", "ecu04">>, <<"ecu10", "ecu08">>, <<"ecu11", "ecu01">>, <<"ecu11", "ecu09">>, <<"ecu13", "ecu12">>, <<"ecu14", "ecu05">>, <<"ecu15", "ecu01">>, <<"ecu15", "ecu03">>, <<"ecu16", "ecu05">>, <<"ecu16", "ecu08">>, <<"ecu19", "ecu08">>}
====
