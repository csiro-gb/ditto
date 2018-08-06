# coding: utf8

###### Read  in the synergi database #######
from .db_parser import DbParser

# Python import
import math
import sys
import os
import json
import numpy as np
import logging
import time
import operator

# Ditto imports #

from ditto.readers.abstract_reader import AbstractReader
from ditto.store import Store
from ditto.models.node import Node
from ditto.models.line import Line
from ditto.models.load import Load
from ditto.models.phase_load import PhaseLoad
from ditto.models.regulator import Regulator
from ditto.models.wire import Wire
from ditto.models.capacitor import Capacitor
from ditto.models.phase_capacitor import PhaseCapacitor
from ditto.models.powertransformer import PowerTransformer
from ditto.models.winding import Winding
from ditto.models.phase_winding import PhaseWinding
from ditto.models.power_source import PowerSource
from ditto.models.position import Position

from ditto.models.base import Unicode

# from ditto.models.recorder import Recorder

logger = logging.getLogger(__name__)


def create_mapping(keys, values, remove_spaces=False):
    if len(keys) != len(values):
        raise ValueError(
            "create_mapping expects keys and values to have the same length."
        )
    if len(keys) != len(np.unique(keys)):
        raise ValueError("create_mapping expects unique keys.")
    if remove_spaces:
        return {k: v.replace(" ", "_") for k, v in zip(keys, values)}
    else:
        return {k: v for k, v in zip(keys, values)}


class Reader(AbstractReader):
    """
    Synergi Reader class.
    """

    register_names = ["synergi", "Synergi", "syn"]

    def __init__(self, **kwargs):
        """Constructor for the Synergi reader."""

        self.input_file = None
        if "input_file" in kwargs:
            self.input_file = kwargs["input_file"]
        else:
            mdb_files = [f for f in os.listdir(".") if f.endswith(".mdb")]
            if len(mdb_files) == 1:
                self.input_file = mdb_files[0]

        # Can provide a ware house database seperated from the main database
        if "warehouse" in kwargs:
            self.ware_house_input_file = kwargs["warehouse"]
        else:
            self.ware_house_input_file = None

        self.SynergiData = None

    def get_data(self, key1, key2):
        """

        """
        if (
            key1 in self.SynergiData.SynergiDictionary
            and key2 in self.SynergiData.SynergiDictionary[key1]
        ):
            return self.SynergiData.SynergiDictionary[key1][key2]
        else:
            print("Could not retrieve data for <{k1}><{k2}>.".format(k1=key1, k2=key2))
            return None

    def parse(self, model):
        """
        Synergi --> DiTTo parse method.
        """
        # ProjectFiles = {"Synegi Circuit Database": self.input_file}
        if self.ware_house_input_file is not None:
            self.SynergiData = DbParser(
                self.input_file, warehouse=self.ware_house_input_file
            )
        else:
            self.SynergiData = DbParser(self.input_file)

        ############ Get the data in #################################################

        ## Feeder ID ##########
        ## This is used to separate different feeders ##
        FeederId = self.get_data("InstFeeders", "FeederId")

        ## Node ###########
        NodeID = self.get_data("Node", "NodeId")
        NodeX = self.get_data("Node", "X")
        NodeY = self.get_data("Node", "Y")

        ## Preferences ########
        LengthUnits = self.get_data("SAI_Equ_Control", "LengthUnits")
        if LengthUnits is not None and len(LengthUnits) == 1:
            LengthUnits = LengthUnits[0]

        ###### Transformer ##################
        TransformerId = self.get_data("InstPrimaryTransformers", "UniqueDeviceId")
        TransformerSectionId = self.get_data("InstPrimaryTransformers", "SectionId")
        TransformerType = self.get_data("InstPrimaryTransformers", "TransformerType")

        DTranId = self.get_data("InstDTrans", "DTranId")
        DTransformerSectionId = self.get_data("InstDTrans", "SectionId")
        HighSideConnCode = self.get_data("InstDTrans", "HighSideConnCode")
        LowSideConnCode = self.get_data("InstDTrans", "LowSideConnCode")
        ConnPhases = self.get_data("InstDTrans", "ConnPhases")

        ## Substration Transformers ##
        SubstationTransformerV = self.get_data(
            "InstSubstationTransformers", "NominalKvll"
        )

        ## Transformer Setting ##
        TransformerTypesinStock = self.get_data("DevTransformers", "TransformerName")
        HighSideRatedKv = self.get_data("DevTransformers", "HighSideRatedKv")
        LowSideRatedKv = self.get_data("DevTransformers", "LowSideRatedKv")
        TransformerRatedKva = self.get_data("DevTransformers", "TransformerRatedKva")
        EmergencyKvaRating = self.get_data("DevTransformers", "EmergencyKvaRating")
        IsThreePhaseUnit = self.get_data("DevTransformers", "IsThreePhaseUnit")
        NoLoadLosses = self.get_data("DevTransformers", "NoLoadLosses")
        PTRatio = self.get_data("DevTransformers", "PTRatio")
        EnableTertiary = self.get_data("DevTransformers", "EnableTertiary")
        TertiaryKva = self.get_data("DevTransformers", "TertiaryKva")
        TertiaryRatedKv = self.get_data("DevTransformers", "TertiaryRatedKv")
        PercentImpedance = self.get_data("DevTransformers", "PercentImpedance")
        PercentResistance = self.get_data("DevTransformers", "PercentResistance")
        ConnectedPhases = self.get_data("InstPrimaryTransformers", "ConnectedPhases")

        # NOTE: When the same information is given in the database and in the warehouse,
        # both are stored and the priority will be given to the information from the
        # network over the one form the warehouse
        #
        # TODO: Check that this is indeed how Synergi works...
        #
        # High side connection code from network
        HighVoltageConnectionCode_N = self.get_data(
            "InstPrimaryTransformers", "HighSideConnectionCode"
        )
        # High side connection code from warehouse
        HighVoltageConnectionCode_W = self.get_data(
            "DevTransformers", "HighVoltageConnectionCode"
        )

        # Low side connection code from network
        LowVoltageConnectionCode_N = self.get_data(
            "InstPrimaryTransformers", "LowSideConnectionCode"
        )
        # Low side connection code from warehouse
        LowVoltageConnectionCode_W = self.get_data(
            "DevTransformers", "LowVoltageConnectionCode"
        )

        # Tertiary connection code from network
        TertConnectCode = self.get_data("InstPrimaryTransformers", "TertConnectCode")
        # Tertiary connection code from warehouse
        TertiaryConnectionCode = self.get_data(
            "DevTransformers", "TertiaryConnectionCode"
        )

        ########## Line #####################
        LineID = self.get_data("InstSection", "SectionId")
        # FeederId = self.get_data("InstSection", "FeederId")
        LineLength = self.get_data("InstSection", "SectionLength_MUL")
        PhaseConductorID = self.get_data("InstSection", "PhaseConductorId")
        PhaseConductor2Id = self.get_data("InstSection", "PhaseConductor2Id")
        PhaseConductor3Id = self.get_data("InstSection", "PhaseConductor3Id")
        NeutralConductorID = self.get_data("InstSection", "NeutralConductorId")
        ConfigurationId = self.get_data("InstSection", "ConfigurationId")
        SectionPhases = self.get_data("InstSection", "SectionPhases")
        LineFeederId = self.get_data("InstSection", "FeederId")
        FromNodeId = self.get_data("InstSection", "FromNodeId")
        ToNodeId = self.get_data("InstSection", "ToNodeId")
        IsFromEndOpen = self.get_data("InstSection", "IsFromEndOpen")
        IsToEndOpen = self.get_data("InstSection", "IsToEndOpen")
        AmpRating = self.get_data("InstSection", "AmpRating")

        # Create mapping between section IDs and Feeder Ids
        self.section_feeder_mapping = create_mapping(
            LineID, LineFeederId, remove_spaces=True
        )

        self.section_phase_mapping = create_mapping(LineID, SectionPhases)

        ## Configuration ########
        ConfigName = self.get_data("DevConfig", "ConfigName")
        Position1_X_MUL = self.get_data("DevConfig", "Position1_X_MUL")
        Position1_Y_MUL = self.get_data("DevConfig", "Position1_Y_MUL")
        Position2_X_MUL = self.get_data("DevConfig", "Position2_X_MUL")
        Position2_Y_MUL = self.get_data("DevConfig", "Position2_Y_MUL")
        Position3_X_MUL = self.get_data("DevConfig", "Position3_X_MUL")
        Position3_Y_MUL = self.get_data("DevConfig", "Position3_Y_MUL")
        Neutral_X_MUL = self.get_data("DevConfig", "Neutral_X_MUL")
        Neutral_Y_MUL = self.get_data("DevConfig", "Neutral_Y_MUL")

        config_mapping = {}
        for idx, conf in enumerate(ConfigName):
            config_mapping[conf] = {
                "Position1_X_MUL": Position1_X_MUL[idx],
                "Position1_Y_MUL": Position1_Y_MUL[idx],
                "Position2_X_MUL": Position2_X_MUL[idx],
                "Position2_Y_MUL": Position2_Y_MUL[idx],
                "Position3_X_MUL": Position3_X_MUL[idx],
                "Position3_Y_MUL": Position3_Y_MUL[idx],
                "Neutral_X_MUL": Neutral_X_MUL[idx],
                "Neutral_Y_MUL": Neutral_Y_MUL[idx],
            }

        ## Wires ###########
        CableGMR = self.get_data("DevConductors", "CableGMR_MUL")
        CableDiamOutside = self.get_data("DevConductors", "CableDiamOutside_SUL")
        CableResistance = self.get_data("DevConductors", "CableResistance_PerLUL")
        ConductorName = self.get_data("DevConductors", "ConductorName")
        PosSequenceResistance_PerLUL = self.get_data(
            "DevConductors", "PosSequenceResistance_PerLUL"
        )
        PosSequenceReactance_PerLUL = self.get_data(
            "DevConductors", "PosSequenceReactance_PerLUL"
        )
        ZeroSequenceResistance_PerLUL = self.get_data(
            "DevConductors", "ZeroSequenceResistance_PerLUL"
        )
        ZeroSequenceReactance_PerLUL = self.get_data(
            "DevConductors", "ZeroSequenceReactance_PerLUL"
        )
        ContinuousCurrentRating = self.get_data(
            "DevConductors", "ContinuousCurrentRating"
        )
        InterruptCurrentRating = self.get_data(
            "DevConductors", "InterruptCurrentRating"
        )

        conductor_mapping = {}
        for idx, cond in enumerate(ConductorName):
            conductor_mapping[cond] = {
                "CableGMR": CableGMR[idx],
                "CableDiamOutside": CableDiamOutside[idx],
                "CableResistance": CableResistance[idx],
                "PosSequenceResistance_PerLUL": PosSequenceResistance_PerLUL[idx],
                "PosSequenceReactance_PerLUL": PosSequenceReactance_PerLUL[idx],
                "ZeroSequenceResistance_PerLUL": ZeroSequenceResistance_PerLUL[idx],
                "ZeroSequenceReactance_PerLUL": ZeroSequenceReactance_PerLUL[idx],
                "ContinuousCurrentRating": ContinuousCurrentRating[idx],
                "InterruptCurrentRating": InterruptCurrentRating[idx],
            }

        ## Loads #############
        LoadName = self.get_data("Loads", "SectionId")
        Phase1Kw = self.get_data("Loads", "Phase1Kw")
        Phase2Kw = self.get_data("Loads", "Phase2Kw")
        Phase3Kw = self.get_data("Loads", "Phase3Kw")
        Phase1Kvar = self.get_data("Loads", "Phase1Kvar")
        Phase2Kvar = self.get_data("Loads", "Phase2Kvar")
        Phase3Kvar = self.get_data("Loads", "Phase3Kvar")

        ## Capacitors ################
        CapacitorSectionID = self.get_data("InstCapacitors", "SectionId")
        CapacitorName = self.get_data("InstCapacitors", "UniqueDeviceId")
        CapacitorVoltage = self.get_data("InstCapacitors", "RatedKv")
        CapacitorConnectionType = self.get_data("InstCapacitors", "ConnectionType")
        CapacitorTimeDelaySec = self.get_data("InstCapacitors", "TimeDelaySec")
        CapacitorPrimaryControlMode = self.get_data(
            "InstCapacitors", "PrimaryControlMode"
        )
        CapacitorModule1CapSwitchCloseValue = self.get_data(
            "InstCapacitors", "Module1CapSwitchCloseValue"
        )
        CapacitorModule1CapSwitchTripValue = self.get_data(
            "InstCapacitors", "Module1CapSwitchTripValue"
        )
        CapacitorPTRatio = self.get_data("InstCapacitors", "CapacitorPTRatio")
        CapacitorCTRating = self.get_data("InstCapacitors", "CapacitorCTRating")
        CapacitorSectionId = self.get_data("InstCapacitors", "SectionId")
        CapacitorFixedKvarPhase1 = self.get_data("InstCapacitors", "FixedKvarPhase1")
        CapacitorFixedKvarPhase2 = self.get_data("InstCapacitors", "FixedKvarPhase2")
        CapacitorFixedKvarPhase3 = self.get_data("InstCapacitors", "FixedKvarPhase3")
        MeteringPhase = self.get_data("InstCapacitors", "MeteringPhase")
        CapacitorConnectedPhases = self.get_data("InstCapacitors", "ConnectedPhases")

        ## Regulators ###################
        RegulatorId = self.get_data("InstRegulators", "UniqueDeviceId")
        RegulatorTimeDelay = self.get_data("InstRegulators", "TimeDelaySec")
        RegulatorTapLimiterHighSetting = self.get_data(
            "InstRegulators", "TapLimiterHighSetting"
        )
        RegulatorTapLimiterLowSetting = self.get_data(
            "InstRegulators", "TapLimiterLowSetting"
        )
        RegulatorTapLimiterLowSetting = self.get_data(
            "InstRegulators", "TapLimiterLowSetting"
        )
        RegulatrorForwardBWDialPhase1 = self.get_data(
            "InstRegulators", "ForwardBWDialPhase1"
        )
        RegulatrorForwardBWDialPhase2 = self.get_data(
            "InstRegulators", "ForwardBWDialPhase2"
        )
        RegulatrorForwardBWDialPhase3 = self.get_data(
            "InstRegulators", "ForwardBWDialPhase3"
        )
        RegulatrorForwardVoltageSettingPhase1 = self.get_data(
            "InstRegulators", "ForwardVoltageSettingPhase1"
        )
        RegulatrorForwardVoltageSettingPhase1 = self.get_data(
            "InstRegulators", "ForwardVoltageSettingPhase1"
        )
        RegulatrorForwardVoltageSettingPhase2 = self.get_data(
            "InstRegulators", "ForwardVoltageSettingPhase2"
        )
        RegulatrorForwardVoltageSettingPhase3 = self.get_data(
            "InstRegulators", "ForwardVoltageSettingPhase3"
        )
        RegulatrorSectionId = self.get_data("InstRegulators", "SectionId")
        RegulagorPhases = self.get_data("InstRegulators", "ConnectedPhases")
        RegulatorTypes = self.get_data("InstRegulators", "RegulatorType")
        RegulatrorNames = self.get_data("DevRegulators", "RegulatorName")
        RegulatorPTRatio = self.get_data("DevRegulators", "PTRatio")
        RegulatorCTRating = self.get_data("DevRegulators", "CTRating")
        RegulatorNearFromNode = self.get_data("InstRegulators", "NearFromNode")

        RegulatorRatedVoltage = self.get_data("DevRegulators", "RegulatorRatedVoltage")
        RegulatorRatedKva = self.get_data("DevRegulators", "RegulatorRatedKva")
        RegulatorNoLoadLosses = self.get_data("DevRegulators", "NoLoadLosses")
        RegulatorConnectionCode = self.get_data("DevRegulators", "ConnectionCode")

        ##### PV ##################################
        PVUniqueDeviceId = self.get_data("InstLargeCust", "UniqueDeviceId")
        PVSectionId = self.get_data("InstLargeCust", "SectionId")
        PVGenType = self.get_data("InstLargeCust", "GenType")
        PVGenPhase1Kw = self.get_data("InstLargeCust", "GenPhase1Kw")
        PVGenPhase2Kw = self.get_data("InstLargeCust", "GenPhase2Kw")
        PVGenPhase3Kw = self.get_data("InstLargeCust", "GenPhase3Kw")

        ## Generators ###############################
        GeneratorSectionID = self.get_data("InstGenerators", "SectionId")
        GeneratorID = self.get_data("InstGenerators", "UniqueDeviceId")
        GeneratorConnectedPhases = self.get_data("InstGenerators", "ConnectedPhases")
        GeneratorMeteringPhase = self.get_data("InstGenerators", "MeteringPhase")
        GeneratorType = self.get_data("InstGenerators", "GeneratorType")
        GeneratorVoltageSetting = self.get_data("InstGenerators", "VoltageSetting")
        GeneratorPF = self.get_data("InstGenerators", "PQPowerFactorPercentage")
        GenPhase1Kw = self.get_data("InstGenerators", "GenPhase1Kw")
        GenPhase1Kvar = self.get_data("InstGenerators", "GenPhase1Kvar")
        GenPhase2Kw = self.get_data("InstGenerators", "GenPhase2Kw")
        GenPhase2Kvar = self.get_data("InstGenerators", "GenPhase2Kvar")
        GenPhase3Kw = self.get_data("InstGenerators", "GenPhase3Kw")
        GenPhase3Kvar = self.get_data("InstGenerators", "GenPhase3Kvar")

        GeneratorName = self.get_data("DevGenerators", "GeneratorName")
        GeneratorTypeDev = self.get_data("DevGenerators", "GeneratorType")
        GeneratorKvRating = self.get_data("DevGenerators", "KvRating")
        GeneratorKwRating = self.get_data("DevGenerators", "KwRating")
        GeneratorPercentPFRating = self.get_data("DevGenerators", "PercentPFRating")

        ######################### Converting to Ditto #################################################

        ## Feeder ID###########
        NFeeder = len(FeederId)

        ######## Converting Node into Ditto##############
        # N = len(NodeID)
        ## Delete the blank spaces in the phases

        SectionPhases01 = []
        tt = 0
        for obj in SectionPhases:
            SectionPhases_thisline1 = list(SectionPhases[tt])
            # SectionPhases_thisline1 = [
            #    s.encode("ascii") for s in SectionPhases_thisline
            # ]
            SectionPhases_thisline2 = [s for s in SectionPhases_thisline1 if s != " "]
            SectionPhases01.append(SectionPhases_thisline2)
            tt = tt + 1

        SectionPhases01 = np.array(SectionPhases01)

        ## Get the good lines
        i = 0
        NodeIDgood = []
        for obj in LineID:
            if IsToEndOpen[i] == 0 and IsFromEndOpen[i] == 0:
                FromNodeID1 = FromNodeId[i]
                # FromNodeID2 = [s.encode("ascii") for s in FromNodeID1]
                # FromNodeID3 = "".join(FromNodeID2)
                FromNodeID3 = FromNodeID1  # .encode("ascii")
                ToNodeID1 = ToNodeId[i]
                # ToNodeID2 = [s.encode("ascii") for s in ToNodeID1]
                # ToNodeID3 = "".join(ToNodeID2)
                ToNodeID3 = ToNodeID1  # .encode("ascii")
                NodeIDgood.append(FromNodeID3)
                NodeIDgood.append(ToNodeID3)
            i = i + 1

        # Convert NodeID to ascii code
        i = 0
        NodeID3 = []
        for obj in NodeID:
            NodeID1 = NodeID[i]
            # NodeID2 = [s.encode("ascii") for s in NodeID1]
            # NodeID3.append("".join(NodeID2))
            NodeID3 = NodeID1  # .encode("ascii")
            i = i + 1

        i = 0
        for obj in NodeID:

            ## Find out if this node is a necessary node
            t = 0
            NodeFlag = 1
            # for obj in NodeIDgood:
            #
            #     if NodeID3[i]==NodeIDgood[t]:
            #         NodeFlag=1
            #         break
            #     t=t+1

            if NodeFlag == 1:

                api_node = Node(model)
                api_node.name = NodeID[i].lower().replace(" ", "_")

                try:
                    api_node.feeder_name = self.section_feeder_mapping[NodeID[i]]
                except:
                    pass

                pos = Position(model)
                pos.long = NodeY[i]
                pos.lat = NodeX[i]
                api_node.positions.append(pos)

                if NodeID[i] == "mikilua 2 tsf":
                    api_node.bustype = "SWING"

                ## Search the nodes in FromNodeID
                tt = 0
                CountFrom = []
                for obj in FromNodeId:
                    Flag = NodeID[i] == FromNodeId[tt]
                    if Flag == True:
                        CountFrom.append(tt)
                    tt = tt + 1

                CountFrom = np.array(CountFrom)

                ## Search in the nodes in ToNodeID
                tt = 0
                CountTo = []
                for obj in ToNodeId:
                    Flag = NodeID[i] == ToNodeId[tt]
                    if Flag == True:
                        CountTo.append(tt)
                    tt = tt + 1

                CountTo = np.array(CountTo)

                PotentialNodePhases = []
                ttt = 0
                if len(CountFrom) > 0:
                    for obj in CountFrom:
                        PotentialNodePhases.append(SectionPhases01[CountFrom[ttt]])
                        tt = tt + 1
                        ttt = ttt + 1

                if len(CountTo) > 0:
                    ttt = 0
                    for obj in CountTo:
                        PotentialNodePhases.append(SectionPhases01[CountTo[ttt]])
                        ttt = ttt + 1

                PhaseLength = []
                tt = 0
                for obj in PotentialNodePhases:
                    PhaseLength.append(len(PotentialNodePhases[tt]))
                    tt = tt + 1

                PhaseLength = np.array(PhaseLength)

                index = np.argmax(PhaseLength).flatten()[0]
                value = np.max(PhaseLength)

                # index, value = max(enumerate(PhaseLength), key=operator.itemgetter(1))

                # SectionPhases_thisline = list(PotentialNodePhases[index])
                # SectionPhases_thisline1 = [s.encode('ascii') for s in SectionPhases_thisline]
                # SectionPhases_thisline2 = filter(str.strip, SectionPhases_thisline1)

                # SectionPhases_thisline = [s.decode('utf-8') for s in SectionPhases_thisline2]
                for p in PotentialNodePhases[index]:
                    api_node.phases.append(p)

                ########### Creat Recorder in  Ditto##############################################

                # recorderphases = list(PotentialNodePhases[index])

                # api_recorder = Recorder(model)
                # api_recorder.name = "recorder" + NodeID[i].lower()
                # api_recorder.parent = NodeID[i].lower()
                # api_recorder.property = "voltage_" + recorderphases[0] + "[kV]"
                # api_recorder.file = "n" + NodeID[i] + ".csv"
                # api_recorder.interval = 50

            i = i + 1

        ########### Converting Line into Ditto##############################################
        i = 0
        for obj in LineID:

            ## Exclude the line with regulators
            # ii=0
            LineFlag = 0
            # for obj in RegulatrorSectionId:
            #     if LineID[i]==RegulatrorSectionId[ii]:
            #         LineFlag=1
            #         break
            #     ii=ii+1

            ## Exclude the line with transformers
            # ii = 0
            # for obj in TransformerSectionId:
            #     if LineID[i] == TransformerSectionId[ii]:
            #         LineFlag = 1
            #         break
            #     ii = ii + 1

            if LineFlag == 0:
                #   if IsToEndOpen[i] ==0 and IsFromEndOpen[i]==0:
                api_line = Line(model)
                api_line.name = LineID[i].lower()

                try:
                    api_line.feeder_name = self.section_feeder_mapping[LineID[i]]
                except:
                    pass

                # Cache configuration
                if ConfigurationId is not None:
                    if (
                        isinstance(ConfigurationId[i], str)
                        and len(ConfigurationId[i]) > 0
                        and ConfigurationId[i] in config_mapping
                    ):
                        config = config_mapping[ConfigurationId[i]]
                    else:
                        config = {}

                # Assumes MUL is medium unit length and this is feets
                # Converts to meters then
                #
                api_line.length = LineLength[i] * 0.3048

                # From element
                api_line.from_element = FromNodeId[i].lower()

                # To element
                api_line.to_element = ToNodeId[i].lower()

                ### Line Phases##################
                SectionPhases_thisline1 = list(SectionPhases[i])
                # SectionPhases_thisline1 = [
                #    s.encode("ascii") for s in SectionPhases_thisline
                # ]
                SectionPhases_thisline = [
                    s for s in SectionPhases_thisline1 if s != " "
                ]
                # SectionPhases_thisline2 = filter(str.strip, SectionPhases_thisline1)

                # SectionPhases_thisline = [
                #    s.decode("utf-8") for s in SectionPhases_thisline2
                # ]
                NPhase = len(SectionPhases_thisline)

                ## The wires belong to this line

                for idx, phase in enumerate(SectionPhases_thisline):

                    api_wire = Wire(model)
                    api_wire.phase = phase

                    # Assumes MUL is medium unit length = ft
                    # Convert to meters
                    #
                    coeff = 0.3048
                    if (
                        idx == 0
                        and phase != "N"
                        and "Position1_X_MUL" in config
                        and "Position1_Y_MUL" in config
                    ):
                        api_wire.X = (
                            config["Position1_X_MUL"] * coeff
                        )  # DiTTo is in meters
                        api_wire.Y = (
                            config["Position1_Y_MUL"] * coeff
                        )  # DiTTo is in meters
                    if (
                        idx == 1
                        and phase != "N"
                        and "Position2_X_MUL" in config
                        and "Position2_Y_MUL" in config
                    ):
                        api_wire.X = (
                            config["Position2_X_MUL"] * coeff
                        )  # DiTTo is in meters
                        api_wire.Y = (
                            config["Position2_Y_MUL"] * coeff
                        )  # DiTTo is in meters
                    if (
                        idx == 2
                        and phase != "N"
                        and "Position3_X_MUL" in config
                        and "Position3_Y_MUL" in config
                    ):
                        api_wire.X = (
                            config["Position3_X_MUL"] * coeff
                        )  # DiTTo is in meters
                        api_wire.Y = (
                            config["Position3_Y_MUL"] * coeff
                        )  # DiTTo is in meters

                    # Looks like zero-height wires are possible in Synergi but not
                    # in some other formats like OpenDSS
                    #
                    if api_wire.Y == 0:
                        api_wire.Y += 0.01

                    # First wire, use PhaseConductorID
                    if (
                        idx == 0
                        and PhaseConductorID is not None
                        and isinstance(PhaseConductorID[i], str)
                        and len(PhaseConductorID[i]) > 0
                    ):
                        api_wire.nameclass = PhaseConductorID[i]

                    # Second wire, if PhaseConductor2Id is provided, use it
                    # Otherwise, assume the phase wires are the same
                    if idx == 1:
                        if (
                            PhaseConductor2Id is not None
                            and isinstance(PhaseConductor2Id[i], str)
                            and len(PhaseConductor2Id[i]) > 0
                        ):
                            api_wire.nameclass = PhaseConductor2Id[i]
                        else:
                            try:
                                api_wire.nameclass = PhaseConductorID[i]
                            except:
                                pass

                    # Same for third wire
                    if idx == 2:
                        if (
                            PhaseConductor3Id is not None
                            and isinstance(PhaseConductor3Id[i], str)
                            and len(PhaseConductor3Id[i]) > 0
                        ):
                            api_wire.nameclass = PhaseConductor3Id[i]
                        else:
                            try:
                                api_wire.nameclass = PhaseConductorID[i]
                            except:
                                pass

                    if (
                        api_wire.nameclass is not None
                        and api_wire.nameclass in conductor_mapping
                    ):
                        api_wire.gmr = (
                            conductor_mapping[api_wire.nameclass]["CableGMR"] * 0.3048
                        )  # DiTTo is in meters and GMR is assumed to be given in feets

                        # Diameter is assumed to be given in inches and is converted to meters here
                        api_wire.diameter = (
                            conductor_mapping[api_wire.nameclass]["CableDiamOutside"]
                            * 0.0254
                        )

                        # Ampacity
                        api_wire.ampacity = conductor_mapping[api_wire.nameclass][
                            "ContinuousCurrentRating"
                        ]

                        # Emergency ampacity
                        api_wire.emergency_ampacity = conductor_mapping[
                            api_wire.nameclass
                        ]["InterruptCurrentRating"]

                        # TODO: Change this once resistance is the per unit length resistance
                        if api_line.length is not None:
                            api_wire.resistance = (
                                conductor_mapping[api_wire.nameclass]["CableResistance"]
                                * api_line.length
                                * 1.0
                                / 1609.34
                            )

                    api_line.wires.append(api_wire)

                # Neutral wire
                # Create a neutral wire if the information is present
                #
                if (
                    NeutralConductorID is not None
                    and isinstance(NeutralConductorID[i], str)
                    and len(NeutralConductorID[i]) > 0
                ):
                    api_wire = Wire(model)

                    # Phase
                    api_wire.phase = "N"

                    # Nameclass
                    api_wire.nameclass = NeutralConductorID[i]

                    # Spacing
                    coeff = 0.3048
                    if "Neutral_X_MUL" in config and "Neutral_Y_MUL" in config:
                        api_wire.X = (
                            config["Neutral_X_MUL"] * coeff
                        )  # DiTTo is in meters
                        api_wire.Y = (
                            config["Neutral_Y_MUL"] * coeff
                        )  # DiTTo is in meters

                    if (
                        api_wire.nameclass is not None
                        and api_wire.nameclass in conductor_mapping
                    ):
                        # GMR
                        api_wire.gmr = (
                            conductor_mapping[api_wire.nameclass]["CableGMR"] * 0.3048
                        )

                        # Diameter
                        api_wire.diameter = (
                            conductor_mapping[api_wire.nameclass]["CableDiamOutside"]
                            * 0.0254
                        )

                        # Ampacity
                        api_wire.ampacity = conductor_mapping[api_wire.nameclass][
                            "ContinuousCurrentRating"
                        ]

                        # Emergency ampacity
                        api_wire.emergency_ampacity = conductor_mapping[
                            api_wire.nameclass
                        ]["InterruptCurrentRating"]

                        # Resistance
                        if api_line.length is not None:
                            api_wire.resistance = (
                                (
                                    conductor_mapping[api_wire.nameclass][
                                        "CableResistance"
                                    ]
                                    * api_line.length
                                )
                                * 1.0
                                / 1609.34
                            )

                    if api_wire.Y == 0:
                        api_wire.Y += 0.01

                    api_line.wires.append(api_wire)

                ## Calculating the impedance matrix of this line

                PhaseConductorIDthisline = PhaseConductorID[i]

                tt = 0
                Count = 0
                impedance_matrix = None

                if ConductorName is not None:
                    for obj in ConductorName:
                        Flag = PhaseConductorIDthisline == ConductorName[tt]
                        if Flag == True:
                            Count = tt
                        tt = tt + 1

                    r1 = PosSequenceResistance_PerLUL[Count]
                    x1 = PosSequenceReactance_PerLUL[Count]
                    r0 = ZeroSequenceResistance_PerLUL[Count]
                    x0 = ZeroSequenceReactance_PerLUL[Count]

                    # In this case, we build the impedance matrix from Z+ and Z0 in the following way:
                    #         __________________________
                    #        | Z0+2*Z+  Z0-Z+   Z0-Z+   |
                    # Z= 1/3 | Z0-Z+    Z0+2*Z+ Z0-Z+   |
                    #        | Z0-Z+    Z0-Z+   Z0+2*Z+ |
                    #         --------------------------

                    # TODO: Check that the following is correct...
                    # If LengthUnits is set to English2 or not defined , then assume miles
                    if LengthUnits == "English2" or LengthUnits is None:
                        coeff = 0.000621371
                    # Else, if LengthUnits is set to English1, assume kft
                    elif LengthUnits == "English1":
                        coeff = 3.28084 * 10 ** -3
                    # Else, if LengthUnits is set to Metric, assume km
                    elif LengthUnits == "Metric":
                        coeff = 10 ** -3
                    else:
                        raise ValueError(
                            "LengthUnits <{}> is not valid.".format(LengthUnits)
                        )

                    coeff *= 1.0 / 3.0

                    if NPhase == 2:
                        impedance_matrix = [[coeff * complex(float(r0), float(x0))]]
                    if NPhase == 3:

                        b1 = float(r0) - float(r1)
                        b2 = float(x0) - float(x1)

                        if b1 < 0:
                            b1 = -b1
                        if b1 == 0:
                            b1 = float(r1)
                        if b2 < 0:
                            b2 = -b2
                        if b2 == 0:
                            b2 = float(x1)

                        b = coeff * complex(b1, b2)

                        a = coeff * complex(
                            (2 * float(r1) + float(r0)), (2 * float(x1) + float(x0))
                        )

                        impedance_matrix = [[a, b], [b, a]]

                    if NPhase == 4:
                        a = coeff * complex(
                            (2 * float(r1) + float(r0)), (2 * float(x1) + float(x0))
                        )
                        b1 = float(r0) - float(r1)
                        b2 = float(x0) - float(x1)

                        if b1 < 0:
                            b1 = -b1
                        if b1 == 0:
                            b1 = float(r1)
                        if b2 < 0:
                            b2 = -b2
                        if b2 == 0:
                            b2 = float(x1)

                        b = coeff * complex(b1, b2)

                        impedance_matrix = [[a, b, b], [b, a, b], [b, b, a]]
                if impedance_matrix is not None:
                    api_line.impedance_matrix = impedance_matrix
                else:
                    print("No impedance matrix for line {}".format(api_line.name))

            i = i + 1

        ######### Converting transformer  into Ditto###############
        i = 0
        for obj in TransformerId:

            api_transformer = PowerTransformer(model)
            api_transformer.name = TransformerId[i].replace(" ", "_").lower()

            try:
                api_transformer.feeder_name = self.section_feeder_mapping[
                    TransformerSectionId[i]
                ]
            except:
                cleaned_id = TransformerSectionId[i].replace("Tran", "").strip()
                try:
                    api_transformer.feeder_name = self.section_feeder_mapping[
                        cleaned_id
                    ]
                except:
                    pass

            TransformerTypethisone = TransformerType[i]
            TransformerSectionIdthisone = TransformerSectionId[i]

            TransformerTypethisone01 = TransformerTypethisone.encode("ascii")
            TransformerSectionIdthisone01 = TransformerSectionIdthisone.encode("ascii")

            # Find out the from and to elements
            tt = 0
            Count = 0
            for obj in LineID:
                Flag = TransformerSectionId[i] == LineID[tt]
                if Flag == True:
                    Count = tt
                tt = tt + 1

            # To element
            api_transformer.to_element = ToNodeId[Count].replace(" ", "_").lower()

            # From element
            api_transformer.from_element = FromNodeId[Count].replace(" ", "_").lower()

            tt = 0
            Count = 0

            if TransformerTypesinStock is not None:

                for obj in TransformerTypesinStock:
                    Flag = TransformerType[i] == TransformerTypesinStock[tt]
                    if Flag == True:
                        Count = tt
                    tt = tt + 1

                # TransformerRatedKvathisone = TransformerRatedKva[Count]
                # api_transformer.powerrating = TransformerRatedKvathisone * 1000
                # api_transformer.primaryvoltage = HighSideRatedKv[Count] * 1000
                # api_transformer.secondaryvoltage = LowSideRatedKv[Count] * 1000

                # HighSideRatedKvthisone = HighSideRatedKv[Count]
                # PercentImpedancethisone = PercentImpedance[Count]
                # PercentResistancethisone = PercentResistance[Count]

                ## Calculate the impedance of this transformer
                # Resistancethisone = (
                #    (HighSideRatedKvthisone ** 2 / TransformerRatedKvathisone * 1000)
                #    * PercentResistancethisone
                #    / 100
                # )
                # Reactancethisone = (
                #    (HighSideRatedKvthisone ** 2 / TransformerRatedKvathisone * 1000)
                #    * (PercentImpedancethisone - PercentResistancethisone)
                #    / 100
                # )

                # transformerimpedance = complex(Resistancethisone, Reactancethisone)
                #            api_transformer.impedance=repr(transformerimpedance)[1:-1]
                # api_transformer.impedance = transformerimpedance

                ## Connection type of the transformer
                # api_transformer.connectiontype = (
                #    HighVoltageConnectionCode[Count] + LowVoltageConnectionCode[Count]
                # )

            # PT Ratio
            api_transformer.pt_ratio = PTRatio[Count]

            # NoLoadLosses
            api_transformer.noload_loss = NoLoadLosses[Count]

            # Number of windings
            # TODO: IS THIS RIGHT???
            #
            if IsThreePhaseUnit[Count] == 1 and EnableTertiary[Count] == 1:
                n_windings = 3
            else:
                n_windings = 2

            phases = self.section_phase_mapping[TransformerSectionId[i]]

            for winding in range(n_windings):

                # Create a new Windign object
                w = Winding(model)

                # Primary
                if winding == 0:

                    # Connection_type
                    if (
                        HighVoltageConnectionCode_N is not None
                        and len(HighVoltageConnectionCode_N[i]) > 0
                    ):
                        w.connection_type = HighVoltageConnectionCode_N[i]
                    elif HighVoltageConnectionCode_W is not None:
                        w.connection_type = HighVoltageConnectionCode_W[Count]

                    # Nominal voltage
                    w.nominal_voltage = (
                        HighSideRatedKv[Count] * 10 ** 3
                    )  # DiTTo in volts

                # Secondary
                elif winding == 1:

                    # Connection_type
                    if (
                        LowVoltageConnectionCode_N is not None
                        and len(LowVoltageConnectionCode_N[i]) > 0
                    ):
                        w.connection_type = LowVoltageConnectionCode_N[i]
                    elif LowVoltageConnectionCode_W is not None:
                        w.connection_type = LowVoltageConnectionCode_W[Count]

                    # Nominal voltage
                    w.nominal_voltage = (
                        LowSideRatedKv[Count] * 10 ** 3
                    )  # DiTTo in volts

                # Tertiary
                elif winding == 2:

                    # Connection_type
                    if TertConnectCode is not None and len(TertConnectCode[i]) > 0:
                        w.connection_type = TertConnectCode[i]
                    elif TertiaryConnectionCode is not None:
                        w.connection_type = TertiaryConnectionCode[Count]

                    # Nominal voltage
                    w.nominal_voltage = (
                        TertiaryRatedKv[Count] * 10 ** 3
                    )  # DiTTo in volts

                # rated power
                if winding == 0 or winding == 1:
                    w.rated_power = (
                        TransformerRatedKva[Count] / float(n_windings) * 10 ** 3
                    )  # DiTTo in Vars
                elif winding == 2:
                    w.rated_power = (
                        TertiaryKva * 10 ** 3
                    )  # TODO: Check that this is correct...

                # emergency power
                w.emergency_power = (
                    EmergencyKvaRating[Count] / float(n_windings) * 10 ** 3
                )  # DiTTo in Vars

                # Create the PhaseWindings
                for phase in phases:
                    if phase != "N":
                        pw = PhaseWinding(model)
                        pw.phase = phase
                        w.phase_windings.append(pw)

                # Append the Winding to the Transformer
                api_transformer.windings.append(w)

            i += 1

        ######### Convert load into Ditto ##############
        N = len(LoadName)
        i = 0
        for obj in LoadName:
            api_load = Load(model)
            api_load.name = "Load_" + LoadName[i].replace(" ", "_").lower()

            try:
                api_load.feeder_name = self.section_feeder_mapping[LoadName[i]]
            except:
                pass

            tt = 0
            Count = 0
            for obj in LineID:
                Flag = LoadName[i] == LineID[tt]
                if Flag == True:
                    Count = tt
                tt = tt + 1

            api_load.connecting_element = ToNodeId[Count].lower()

            ## Load at each phase
            PLoad = map(lambda x: x * 10 ** 3, [Phase1Kw[i], Phase2Kw[i], Phase3Kw[i]])
            QLoad = map(
                lambda x: x * 10 ** 3, [Phase1Kvar[i], Phase2Kvar[i], Phase3Kvar[i]]
            )

            for P, Q, phase in zip(PLoad, QLoad, ["A", "B", "C"]):
                if P != 0 or Q != 0:
                    phase_load = PhaseLoad(model)
                    phase_load.phase = phase
                    phase_load.p = P
                    phase_load.q = Q
                    api_load.phase_loads.append(phase_load)

            i += 1

        ####### Convert the capacitor data into Ditto ##########

        i = 0
        for obj in CapacitorName:
            api_cap = Capacitor(model)
            api_cap.name = CapacitorName[i].replace(" ", "_").lower()

            try:
                api_cap.feeder_name = self.section_feeder_mapping[CapacitorSectionId[i]]
            except:
                pass

            control_mode_mapping = {
                "VOLTS": "voltage"
            }  # TODO: Complete the mapping with other control modes

            api_cap.nominal_voltage = CapacitorVoltage[i] * 1000
            api_cap.connection_type = CapacitorConnectionType[i]
            api_cap.delay = CapacitorTimeDelaySec[i]
            if CapacitorPrimaryControlMode[i] in control_mode_mapping:
                api_cap.mode = control_mode_mapping[CapacitorPrimaryControlMode[i]]
            else:
                api_cap.mode = "voltage"  # Default sets to voltage
            api_cap.low = CapacitorModule1CapSwitchCloseValue[i]
            api_cap.high = CapacitorModule1CapSwitchTripValue[i]
            api_cap.pt_ratio = CapacitorPTRatio[i]
            api_cap.ct_ratio = CapacitorCTRating[i]

            # Measuring element
            api_cap.measuring_element = "Line." + CapacitorSectionID[i].lower()

            # PT phase
            api_cap.pt_phase = MeteringPhase[i]

            ## Find out the connecting bus
            tt = 0
            Count = 0
            for obj in LineID:
                Flag = CapacitorSectionId[i] == LineID[tt]
                if Flag == True:
                    Count = tt
                tt = tt + 1

            api_cap.connecting_element = ToNodeId[Count].lower()

            QCap = [
                float(CapacitorFixedKvarPhase1[i]),
                float(CapacitorFixedKvarPhase2[i]),
                float(CapacitorFixedKvarPhase3[i]),
            ]

            t = 0
            Caps = []
            if len(CapacitorConnectedPhases[i]) > 0:
                PhasesthisCap = CapacitorConnectedPhases[i]
            else:
                PhasesthisCap = ["A", "B", "C"]
            for obj in PhasesthisCap:
                phase_caps = PhaseCapacitor(model)
                phase_caps.phase = PhasesthisCap[t]
                phase_caps.var = QCap[t] * 1000
                Caps.append(phase_caps)
                t = t + 1
            api_cap.phase_capacitors = Caps

            i = i + 1

        ########## Convert regulator into Ditto #########
        i = 0
        for obj in RegulatorId:
            api_regulator = Regulator(model)
            api_regulator.name = RegulatorId[i].replace(" ", "_").lower()

            try:
                api_regulator.feeder_name = self.section_feeder_mapping[RegulatorId[i]]
            except:
                cleaned_id = RegulatorId[i].replace("Reg", "").strip()
                try:
                    api_regulator.feeder_name = self.section_feeder_mapping[cleaned_id]
                except:
                    pass

            api_regulator.delay = RegulatorTimeDelay[i]
            api_regulator.highstep = int(RegulatorTapLimiterHighSetting[i])
            api_regulator.lowstep = -int(RegulatorTapLimiterLowSetting[i])

            ## Regulator phases
            # RegulagorPhases_this = list(RegulagorPhases[i])
            # RegulagorPhases_this01 = [s.encode('ascii') for s in RegulagorPhases_this]
            # RegulagorPhases_this02 = filter(str.strip, RegulagorPhases_this01)
            # api_regulator.phases=''.join(RegulagorPhases_this02)
            # api_regulator.pt_phase=RegulagorPhases[i]

            if RegulagorPhases[i] == "A":
                api_regulator.bandwidth = RegulatrorForwardBWDialPhase1[i]
                api_regulator.bandcenter = RegulatrorForwardVoltageSettingPhase1[i]

            if RegulagorPhases[i] == "B":
                api_regulator.bandwidth = RegulatrorForwardBWDialPhase2[i]
                api_regulator.bandcenter = RegulatrorForwardVoltageSettingPhase2[i]

            if RegulagorPhases[i] == "C":
                api_regulator.bandwidth = RegulatrorForwardBWDialPhase3[i]
                api_regulator.bandcenter = RegulatrorForwardVoltageSettingPhase3[i]

            RegulatorTypethisone = RegulatorTypes[i]

            ## Find out pt ratio and ct rating
            Count = None
            if RegulatrorNames is not None:
                for idx, obj in enumerate(RegulatrorNames):
                    if RegulatorTypethisone == obj:
                        Count = idx

            if Count is not None:
                api_regulator.pt_ratio = RegulatorPTRatio[Count]
                api_regulator.ct_ratio = RegulatorCTRating[Count]

            n_windings = 2
            for winding in range(n_windings):
                w = Winding(model)
                if Count is not None:
                    # Connection type
                    w.connection_type = RegulatorConnectionCode[Count]

                    # Nominal voltage
                    w.nominal_voltage = RegulatorRatedVoltage[Count]

                    # Rated Power
                    w.rated_power = (
                        RegulatorRatedKva[Count] / float(n_windings) * 10 ** 3
                    )

                for phase in RegulagorPhases[i]:
                    if phase != "N":
                        pw = PhaseWinding(model)
                        pw.phase = phase

                        # Add PhaseWinding to the winding
                        w.phase_windings.append(pw)

                # Add winding to the regulator
                api_regulator.windings.append(w)

            ## Find out the from and to elements
            Count = None
            for idx, obj in enumerate(LineID):
                if RegulatrorSectionId[i] == obj:
                    Count = idx

            if Count is not None:
                if RegulatorNearFromNode[i] == 0:
                    RegualatorFromNodeID = ToNodeId[Count].lower() + "_1"
                    RegualatorToNodeID = ToNodeId[Count].lower()
                    DummyNodeID = ToNodeId[Count].lower() + "_1"

                if RegulatorNearFromNode[i] == 1:
                    RegualatorFromNodeID = FromNodeId[Count].lower()
                    RegualatorToNodeID = FromNodeId[Count].lower() + "_1"
                    DummyNodeID = FromNodeId[Count].lower() + "_1"

                api_regulator.from_element = RegualatorFromNodeID
                api_regulator.to_element = RegualatorToNodeID

                ## Create the dummy node connecting the regulators
                api_node = Node(model)
                api_node.name = DummyNodeID.lower()
                for p in SectionPhases01[Count]:
                    api_node.phases.append(p)

                ## Create a line to put regulator in lines
                api_line = Line(model)
                api_line.name = LineID[Count].lower()
                api_line.length = LineLength[Count] * 0.3048
                api_line.from_element = FromNodeId[Count].lower()
                api_line.to_element = ToNodeId[Count].lower()

                ### Line Phases##################
                SectionPhases_thisline = SectionPhases01[Count]
                NPhase = len(SectionPhases_thisline)

                ## The wires belong to this line
                t = 0
                wires = []
                for obj in SectionPhases_thisline:
                    api_wire = Wire(model)
                    api_wire.phase = SectionPhases_thisline[t]
                    wires.append(api_wire)
                    t = t + 1

                ## Calculating the impedance matrix of this line

                PhaseConductorIDthisline = PhaseConductorID[Count]

                tt = 0
                Count_Conductor = 0
                impedance_matrix = None

                if ConductorName is not None:
                    for obj in ConductorName:
                        Flag = PhaseConductorIDthisline == ConductorName[tt]
                        if Flag == True:
                            Count_Conductor = tt
                        tt = tt + 1

                    r1 = PosSequenceResistance_PerLUL[Count_Conductor]
                    x1 = PosSequenceReactance_PerLUL[Count_Conductor]
                    r0 = ZeroSequenceResistance_PerLUL[Count_Conductor]
                    x0 = ZeroSequenceReactance_PerLUL[Count_Conductor]

                    coeff = 10 ** -3
                    if NPhase == 2:
                        impedance_matrix = [[coeff * complex(float(r0), float(x0))]]
                    if NPhase == 3:
                        a = coeff * complex(
                            2 * float(r1) + float(r0), 2 * float(x1) + float(x0)
                        )

                        b1 = float(r0) - float(r1)
                        b2 = float(x0) - float(x1)

                        if b1 < 0:
                            b1 = -b1
                        if b1 == 0:
                            b1 = float(r1)
                        if b2 < 0:
                            b2 = -b2
                        if b2 == 0:
                            b2 = float(x1)

                        b = coeff * complex(b1, b2)
                        impedance_matrix = [[a, b], [b, a]]

                    if NPhase == 4:
                        a = coeff * complex(
                            2 * float(r1) + float(r0), 2 * float(x1) + float(x0)
                        )

                        b1 = float(r0) - float(r1)
                        b2 = float(x0) - float(x1)

                        if b1 < 0:
                            b1 = -b1
                        if b1 == 0:
                            b1 = float(r1)
                        if b2 < 0:
                            b2 = -b2
                        if b2 == 0:
                            b2 = float(x1)

                        b = coeff * complex(b1, b2)

                        impedance_matrix = [[a, b, b], [b, a, b], [b, b, a]]

                api_line.wires = wires
                if impedance_matrix is not None:
                    api_line.impedance_matrix = impedance_matrix
                else:
                    print("No impedance matrix for line {}".format(api_line.name))
            i = i + 1

        ##### Convert PV to Ditto###################################

        i = 0
        for obj in PVUniqueDeviceId:
            Flag = PVGenType[i] == "PhotoVoltaic"
            if Flag == True:
                api_PV = PowerSource(model)
                api_PV.name = PVUniqueDeviceId[i].replace(" ", "_").lower()

                try:
                    api_PV.feeder_name = self.section_feeder_mapping[
                        PVUniqueDeviceId[i]
                    ]
                except:
                    pass

                if PVGenPhase1Kw[i] != 0:
                    api_PV.phases = ["A"]
                    api_PV.rated_power = PVGenPhase1Kw[i]
                if PVGenPhase1Kw[i] != 0:
                    api_PV.phases = ["B"]
                    api_PV.rated_power = PVGenPhase2Kw[i]
                if PVGenPhase1Kw[i] != 0:
                    api_PV.phases = ["C"]
                    api_PV.rated_power = PVGenPhase3Kw[i]
            ## Find out the from and to elements
            tt = 0
            Count = 0
            for obj in LineID:
                Flag = PVSectionId[i] == LineID[tt]
                if Flag == True:
                    Count = tt
                tt = tt + 1
            api_PV.connecting_element = ToNodeId[Count]

        for idx, obj in enumerate(GeneratorSectionID):
            Count = None
            for k, obj in enumerate(GeneratorName):
                if GeneratorType[i] == obj:
                    Count = k
            if Count is not None and GeneratorTypeDev[Count] == "PV":
                api_PV = PowerSource(model)

                # PV name
                api_PV.name = GeneratorSectionID[i].lower()

                # Rated Power
                api_PV.rated_power = GeneratorKwRating[Count] * 10 ** 3

                # Connecting element
                Count = None
                for k, obj in enumerate(LineID):
                    if GeneratorSectionID[i] == obj:
                        Count = k
                api_PV.connecting_element = ToNodeId[Count].lower()

                # Nominal voltage
                api_PV.nominal_voltage = GeneratorVoltageSetting[i] * 10 ** 3

                # Phases
                for phase in GeneratorConnectedPhases[i].strip():
                    api_PV.phases.append(phase)

                # Power Factor
                api_PV.power_factor = GeneratorPF[i]
